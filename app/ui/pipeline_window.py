import os
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk

from app.config.paths import DATA_DIR
from app.core.google_drive_loader import FOLDER_TO_TIPO, descargar_datasets_desde_drive
from app.core.mysql_snies_setup import insertar_datos_csv
from app.core.preprocessing_service import preprocesar_csv_maestro


@dataclass
class PipelineResultado:
    categoria: str
    ok: bool
    etapa: str
    detalle: str = ""


class PipelineStageError(RuntimeError):
    def __init__(self, categoria: str, etapa: str, detalle: str):
        super().__init__(detalle)
        self.categoria = categoria
        self.etapa = etapa
        self.detalle = detalle


class VentanaPipelineCategorias:
    TITULO = "Pipeline automatico por categorias"
    EXTENSIONES_VALIDAS = {".xlsx", ".xls", ".csv"}

    def __init__(self, parent: tk.Tk, app):
        self.parent = parent
        self.app = app
        self.running = False

        existente = self._buscar_ventana_existente()
        if existente is not None:
            existente.lift()
            existente.focus_force()
            return

        self.win = tk.Toplevel(parent)
        self.win.title(self.TITULO)
        self.win.geometry("1120x760")
        self.win.minsize(920, 620)
        self.win.configure(bg="white")
        self.win.transient(parent)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self.folder_var = tk.StringVar(value=os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip())
        cred_env = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON_PATH", "").strip()
        self.cred_var = tk.StringVar(value=os.path.expanduser(cred_env) if cred_env else "")
        self.status_var = tk.StringVar(value="Listo. Seleccione categorias y ejecute el pipeline.")

        self.category_vars = {
            categoria: tk.BooleanVar(value=True)
            for categoria in self.app.tipos
        }
        self.controls_a_bloquear: list[tk.Widget] = []

        self._crear_interfaz()

    def _buscar_ventana_existente(self):
        for widget in self.parent.winfo_children():
            if isinstance(widget, tk.Toplevel) and str(widget.title()) == self.TITULO:
                return widget
        return None

    def _crear_interfaz(self):
        config_frame = ttk.Frame(self.win, padding=12)
        config_frame.pack(fill=tk.X)

        ttk.Label(config_frame, text="ID carpeta Drive:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        entry_folder = ttk.Entry(config_frame, textvariable=self.folder_var)
        entry_folder.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(config_frame, text="Credenciales JSON:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        entry_cred = ttk.Entry(config_frame, textvariable=self.cred_var)
        entry_cred.grid(row=1, column=1, sticky="ew", pady=4)
        btn_cred = ttk.Button(config_frame, text="Seleccionar...", command=self._seleccionar_credenciales)
        btn_cred.grid(row=1, column=2, padx=(8, 0), pady=4)

        config_frame.columnconfigure(1, weight=1)

        categorias_frame = ttk.Frame(self.win, padding=(12, 0, 12, 8))
        categorias_frame.pack(fill=tk.X)

        ttk.Label(
            categorias_frame,
            text="Categorias a procesar (el pipeline se ejecuta una por una):",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        checkboxes = []
        for idx, categoria in enumerate(self.app.tipos):
            row = idx // 2 + 1
            col = idx % 2
            chk = ttk.Checkbutton(categorias_frame, text=categoria, variable=self.category_vars[categoria])
            chk.grid(row=row, column=col, sticky="w", padx=(0, 18), pady=2)
            checkboxes.append(chk)

        acciones_cat = ttk.Frame(categorias_frame)
        acciones_cat.grid(row=1, column=2, rowspan=4, sticky="ne", padx=(0, 0))
        btn_todas = ttk.Button(
            acciones_cat,
            text="Seleccionar todas",
            command=lambda: self._seleccionar_todas(True),
            style="Accent.TButton",
        )
        btn_todas.pack(fill=tk.X, pady=(0, 4))
        btn_ninguna = ttk.Button(
            acciones_cat,
            text="Limpiar seleccion",
            command=lambda: self._seleccionar_todas(False),
        )
        btn_ninguna.pack(fill=tk.X)

        control_frame = ttk.Frame(self.win, padding=(12, 0, 12, 8))
        control_frame.pack(fill=tk.X)

        self.btn_iniciar = ttk.Button(
            control_frame,
            text="Iniciar pipeline",
            command=self.iniciar_pipeline,
            style="Success.TButton",
        )
        self.btn_iniciar.pack(side="left")

        self.btn_cerrar = ttk.Button(control_frame, text="Cerrar", command=self._on_close)
        self.btn_cerrar.pack(side="right")

        log_frame = ttk.Frame(self.win, padding=(12, 0, 12, 8))
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            font=("Consolas", 9),
            bg="#fcfcfc",
            relief="solid",
            borderwidth=1,
            state="disabled",
        )
        vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        status_lbl = ttk.Label(self.win, textvariable=self.status_var, anchor="w", background="white")
        status_lbl.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.controls_a_bloquear.extend([entry_folder, entry_cred, btn_cred, btn_todas, btn_ninguna, self.btn_iniciar])
        self.controls_a_bloquear.extend(checkboxes)

    def _set_running(self, is_running: bool):
        self.running = is_running
        nuevo_estado = "disabled" if is_running else "normal"
        for widget in self.controls_a_bloquear:
            try:
                widget.configure(state=nuevo_estado)
            except Exception:
                pass
        if is_running:
            self.btn_cerrar.configure(state="disabled")
        else:
            self.btn_cerrar.configure(state="normal")

    def _on_close(self):
        if self.running:
            messagebox.showinfo(
                "Pipeline en ejecucion",
                "Espere a que finalice el pipeline para cerrar esta ventana.",
                parent=self.win,
            )
            return
        self.win.destroy()

    def _seleccionar_credenciales(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar credenciales de servicio (JSON)",
            filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")],
            parent=self.win,
        )
        if ruta:
            self.cred_var.set(ruta)

    def _seleccionar_todas(self, value: bool):
        for var in self.category_vars.values():
            var.set(value)

    def _obtener_categorias_seleccionadas(self) -> list[str]:
        return [
            categoria
            for categoria, var in self.category_vars.items()
            if bool(var.get())
        ]

    def _work_dir(self) -> str:
        path = os.path.join(DATA_DIR, "gdrive_import")
        os.makedirs(path, exist_ok=True)
        return path

    def _listar_archivos_locales_por_categoria(self) -> dict[str, set[str]]:
        resultado: dict[str, set[str]] = {}
        base = self._work_dir()

        for carpeta_drive, categoria in FOLDER_TO_TIPO.items():
            carpeta_local = os.path.join(base, carpeta_drive)
            if not os.path.isdir(carpeta_local):
                continue

            for nombre in os.listdir(carpeta_local):
                ruta = os.path.join(carpeta_local, nombre)
                if not os.path.isfile(ruta):
                    continue

                ext = os.path.splitext(nombre)[1].lower()
                if ext not in self.EXTENSIONES_VALIDAS:
                    continue

                if categoria not in resultado:
                    resultado[categoria] = set()
                resultado[categoria].add(ruta)

        return resultado

    def _log(self, msg: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {msg}"
        print(f"[Pipeline] {line}")

        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)

        self.status_var.set(msg)
        self.app.status_var.set(f"Pipeline: {msg}")
        self.win.update_idletasks()

    def _limpiar_logs(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def iniciar_pipeline(self):
        if self.running:
            return

        categorias = self._obtener_categorias_seleccionadas()
        if not categorias:
            messagebox.showwarning(
                "Pipeline",
                "Seleccione al menos una categoria para ejecutar el pipeline.",
                parent=self.win,
            )
            return

        folder_id = self.folder_var.get().strip()
        if not folder_id:
            messagebox.showwarning(
                "Pipeline",
                "Ingrese el ID de carpeta de Google Drive.",
                parent=self.win,
            )
            return

        cred_path = os.path.expanduser(self.cred_var.get().strip())
        if not cred_path:
            messagebox.showwarning(
                "Pipeline",
                "Seleccione el archivo de credenciales JSON.",
                parent=self.win,
            )
            return

        if not os.path.exists(cred_path):
            messagebox.showerror(
                "Pipeline",
                f"No se encontro el archivo de credenciales:\n{cred_path}",
                parent=self.win,
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar pipeline",
            (
                "Se ejecutara el pipeline por categoria en este orden:\n"
                + "\n".join(f"- {cat}" for cat in categorias)
                + "\n\nEste proceso puede tardar varios minutos."
            ),
            parent=self.win,
        )
        if not confirmar:
            return

        self._limpiar_logs()
        self._set_running(True)

        try:
            resultados = self._ejecutar_pipeline(categorias, folder_id, cred_path)
            self._mostrar_resumen(resultados)
        except PipelineStageError as exc:
            self._log(
                f"FALLO GLOBAL en etapa '{exc.etapa}': {exc.detalle}",
                level="ERROR",
            )
            messagebox.showerror(
                "Pipeline fallido",
                (
                    "El pipeline fallo antes de procesar categorias.\n\n"
                    f"Etapa: {exc.etapa}\n"
                    f"Detalle: {exc.detalle}"
                ),
                parent=self.win,
            )
        finally:
            self._set_running(False)

    def _ejecutar_pipeline(self, categorias: list[str], folder_id: str, cred_path: str) -> list[PipelineResultado]:
        self._log("Paso 1/4: buscando y descargando archivos nuevos desde Google Drive...")
        archivos_antes = self._listar_archivos_locales_por_categoria()

        try:
            descargar_datasets_desde_drive(
                folder_id,
                cred_path,
                self._work_dir(),
                sobrescribir_existentes=False,
                progress_cb=lambda msg: self._log(msg, level="DRIVE"),
            )
        except Exception as exc:
            raise PipelineStageError("GLOBAL", "descarga_drive", str(exc)) from exc

        archivos_despues = self._listar_archivos_locales_por_categoria()
        nuevos_por_categoria: dict[str, list[str]] = {}
        for categoria in categorias:
            antes = archivos_antes.get(categoria, set())
            despues = archivos_despues.get(categoria, set())
            nuevos_por_categoria[categoria] = sorted(despues - antes)

        total_nuevos = sum(len(rutas) for rutas in nuevos_por_categoria.values())
        self._log(f"Descarga completada. Archivos nuevos detectados: {total_nuevos}")

        resultados: list[PipelineResultado] = []
        for categoria in categorias:
            self._log(f"Procesando categoria: {categoria}")
            try:
                self._procesar_categoria(categoria, nuevos_por_categoria.get(categoria, []))
                resultados.append(PipelineResultado(categoria=categoria, ok=True, etapa="completado"))
            except PipelineStageError as exc:
                self._log(
                    f"[{categoria}] FALLA en etapa '{exc.etapa}': {exc.detalle}",
                    level="ERROR",
                )
                resultados.append(
                    PipelineResultado(
                        categoria=categoria,
                        ok=False,
                        etapa=exc.etapa,
                        detalle=exc.detalle,
                    )
                )
            except Exception as exc:
                detalle = str(exc)
                self._log(
                    f"[{categoria}] FALLA inesperada: {detalle}",
                    level="ERROR",
                )
                resultados.append(
                    PipelineResultado(
                        categoria=categoria,
                        ok=False,
                        etapa="desconocida",
                        detalle=detalle,
                    )
                )

        self.app.actualizar_info()
        return resultados

    def _procesar_categoria(self, categoria: str, archivos_nuevos: list[str]):
        self.app.tipo_seleccionado.set(categoria)

        etapa = "integracion_csv_maestro"
        if archivos_nuevos:
            self._log(
                f"[{categoria}] Paso 2/4: integrando {len(archivos_nuevos)} archivo(s) nuevo(s) al CSV maestro.",
                level="PIPELINE",
            )
            for ruta in archivos_nuevos:
                nombre = os.path.basename(ruta)
                self._log(f"[{categoria}] Integrando archivo: {nombre}", level="PIPELINE")
                ok = self.app.procesar_un_archivo(
                    ruta,
                    tipo_forzado=categoria,
                    confirmar_encabezados=False,
                    reemplazar_duplicados=True,
                    show_ui_errors=False,
                    permitir_año_manual=False,
                )
                if not ok:
                    raise PipelineStageError(
                        categoria,
                        etapa,
                        f"No se pudo integrar el archivo '{nombre}'.",
                    )
        else:
            self._log(
                (
                    f"[{categoria}] Paso 2/4: no se detectaron archivos nuevos. "
                    "Se continuara con limpieza e insercion del CSV maestro actual."
                ),
                level="WARN",
            )

        etapa = "limpieza_csv"
        csv_path = self.app._csv_path(categoria)
        if not os.path.exists(csv_path):
            raise PipelineStageError(
                categoria,
                etapa,
                "No existe CSV maestro para esta categoria.",
            )

        self._log(f"[{categoria}] Paso 3/4: limpiando CSV maestro...", level="PIPELINE")
        try:
            df_limpio = preprocesar_csv_maestro(csv_path)
            filas_limpias = len(df_limpio)
        except Exception as exc:
            raise PipelineStageError(categoria, etapa, str(exc)) from exc

        # Forzar recarga del resumen para reflejar el CSV limpio.
        self.app.data.pop(categoria, None)
        self.app._cargar_datos_completos(categoria)
        self.app.actualizar_info()
        self._log(f"[{categoria}] Limpieza completada. Filas resultantes: {filas_limpias}", level="PIPELINE")

        etapa = "insercion_mysql"
        self._log(
            f"[{categoria}] Paso 4/4: insertando datos limpios en MySQL...",
            level="PIPELINE",
        )
        ok_mysql = insertar_datos_csv(
            progress_cb=lambda msg, c=categoria: self._log(f"[{c}] {msg}", level="MYSQL"),
            recreate=True,
        )
        if not ok_mysql:
            raise PipelineStageError(
                categoria,
                etapa,
                "insertar_datos_csv retorno False. Revise los logs MySQL para mas detalle.",
            )

        self._log(f"[{categoria}] Categoria completada correctamente.", level="OK")

    def _mostrar_resumen(self, resultados: list[PipelineResultado]):
        total = len(resultados)
        exitos = sum(1 for r in resultados if r.ok)
        fallos = total - exitos

        if fallos == 0:
            self._log(f"Pipeline finalizado sin errores. Categorias exitosas: {exitos}/{total}", level="OK")
            messagebox.showinfo(
                "Pipeline completado",
                f"Pipeline finalizado correctamente.\nCategorias procesadas: {exitos}/{total}",
                parent=self.win,
            )
            return

        self._log(
            f"Pipeline finalizado con errores. Exitos: {exitos} | Fallos: {fallos}",
            level="WARN",
        )
        detalle = "\n".join(
            f"- {r.categoria} | etapa: {r.etapa} | detalle: {r.detalle}"
            for r in resultados
            if not r.ok
        )
        messagebox.showwarning(
            "Pipeline con fallos",
            (
                f"El pipeline termino con errores.\n\n"
                f"Categorias exitosas: {exitos}\n"
                f"Categorias con fallo: {fallos}\n\n"
                f"Detalle de fallos:\n{detalle}"
            ),
            parent=self.win,
        )
