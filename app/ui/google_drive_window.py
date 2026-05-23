import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.config.paths import DATA_DIR
from app.core.google_drive_loader import FOLDER_TO_TIPO, descargar_datasets_desde_drive


class VentanaGoogleDriveImport:
    """Ventana dedicada para descarga desde Drive y carga selectiva al CSV master."""

    TITULO = "Gestor de importación Google Drive"

    def __init__(self, parent: tk.Tk, app):
        self.parent = parent
        self.app = app

        existente = self._buscar_ventana_existente()
        if existente is not None:
            existente.lift()
            existente.focus_force()
            return

        self.win = tk.Toplevel(parent)
        self.win.title(self.TITULO)
        self.win.geometry("1080x680")
        self.win.minsize(920, 560)
        self.win.configure(bg="white")
        self.win.transient(parent)

        self.folder_var = tk.StringVar(value=os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip())
        cred_env = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON_PATH", "").strip()
        self.cred_var = tk.StringVar(value=os.path.expanduser(cred_env) if cred_env else "")
        self.categoria_var = tk.StringVar(value="Todas")
        self.status_var = tk.StringVar(value="Listo. Descargue o recargue para ver archivos en gdrive_import.")

        self.path_map = {}
        self.extensiones_validas = {".xlsx", ".xls", ".csv"}

        self._crear_interfaz()
        self._recargar_tabla()

    def _buscar_ventana_existente(self):
        for widget in self.parent.winfo_children():
            if isinstance(widget, tk.Toplevel) and str(widget.title()) == self.TITULO:
                return widget
        return None

    def _crear_interfaz(self):
        top_frame = ttk.Frame(self.win, padding=12)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="ID carpeta Drive:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(top_frame, textvariable=self.folder_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(top_frame, text="Credenciales JSON:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(top_frame, textvariable=self.cred_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(top_frame, text="Seleccionar...", command=self._seleccionar_credenciales).grid(row=1, column=2, padx=(8, 0), pady=4)
        top_frame.columnconfigure(1, weight=1)

        actions_frame = ttk.Frame(self.win, padding=(12, 0, 12, 8))
        actions_frame.pack(fill=tk.X)
        ttk.Button(actions_frame, text="Descargar solo nuevos", style="Primary.TButton", command=lambda: self._descargar_desde_drive(False)).pack(side="left", padx=(0, 8))
        ttk.Button(actions_frame, text="Descargar y sobrescribir todo", style="Warning.TButton", command=lambda: self._descargar_desde_drive(True)).pack(side="left", padx=(0, 8))
        ttk.Button(actions_frame, text="Recargar carpeta gdrive_import", style="Accent.TButton", command=self._recargar_tabla).pack(side="left", padx=(0, 8))
        ttk.Button(actions_frame, text="Seleccionar todo", command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side="left", padx=(0, 8))
        ttk.Button(actions_frame, text="Limpiar selección", command=lambda: self.tree.selection_remove(self.tree.selection())).pack(side="left")

        category_frame = ttk.Frame(self.win, padding=(12, 0, 12, 8))
        category_frame.pack(fill=tk.X)
        ttk.Label(category_frame, text="Selección por categoría:").pack(side="left", padx=(0, 8))
        self.cb_categoria = ttk.Combobox(category_frame, textvariable=self.categoria_var, state="readonly", width=42)
        self.cb_categoria.pack(side="left", padx=(0, 8))
        self.cb_categoria["values"] = ["Todas"]
        ttk.Button(
            category_frame,
            text="Seleccionar categoría",
            command=self._seleccionar_por_categoria,
            style="Accent.TButton",
        ).pack(side="left")

        table_frame = ttk.Frame(self.win, padding=(12, 0, 12, 8))
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("tipo", "archivo", "carpeta", "ruta")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("tipo", text="Categoría")
        self.tree.heading("archivo", text="Archivo")
        self.tree.heading("carpeta", text="Carpeta Drive")
        self.tree.heading("ruta", text="Ruta relativa")
        self.tree.column("tipo", width=220, anchor="w")
        self.tree.column("archivo", width=250, anchor="w")
        self.tree.column("carpeta", width=220, anchor="w")
        self.tree.column("ruta", width=300, anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        bottom_frame = ttk.Frame(self.win, padding=(12, 0, 12, 10))
        bottom_frame.pack(fill=tk.X)
        ttk.Button(
            bottom_frame,
            text="Cargar seleccionados al CSV master",
            style="Success.TButton",
            command=self._cargar_seleccionados_al_master,
        ).pack(side="left")
        ttk.Button(bottom_frame, text="Cerrar", command=self.win.destroy).pack(side="right")

        status_lbl = ttk.Label(self.win, textvariable=self.status_var, anchor="w", background="white")
        status_lbl.pack(fill=tk.X, padx=12, pady=(0, 10))

    def _log(self, msg: str):
        print(f"[GoogleDrive] {msg}")
        self.status_var.set(msg)
        self.app.status_var.set(msg)
        self.win.update_idletasks()

    def _work_dir(self) -> str:
        path = os.path.join(DATA_DIR, "gdrive_import")
        os.makedirs(path, exist_ok=True)
        return path

    def _listar_archivos_locales(self):
        archivos = []
        base = self._work_dir()
        for carpeta_drive, tipo in FOLDER_TO_TIPO.items():
            carpeta_local = os.path.join(base, carpeta_drive)
            if not os.path.isdir(carpeta_local):
                continue
            for nombre in sorted(os.listdir(carpeta_local)):
                ruta = os.path.join(carpeta_local, nombre)
                if not os.path.isfile(ruta):
                    continue
                ext = os.path.splitext(nombre)[1].lower()
                if ext not in self.extensiones_validas:
                    continue
                archivos.append(
                    {
                        "tipo": tipo,
                        "carpeta": carpeta_drive,
                        "archivo": nombre,
                        "ruta": ruta,
                    }
                )
        return archivos

    def _recargar_tabla(self):
        self.path_map.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        registros = self._listar_archivos_locales()
        categorias = sorted({reg["tipo"] for reg in registros})
        valores_categoria = ["Todas"] + categorias
        self.cb_categoria["values"] = valores_categoria
        if self.categoria_var.get() not in valores_categoria:
            self.categoria_var.set("Todas")

        for idx, reg in enumerate(registros, start=1):
            iid = str(idx)
            rel = os.path.relpath(reg["ruta"], DATA_DIR)
            self.tree.insert("", "end", iid=iid, values=(reg["tipo"], reg["archivo"], reg["carpeta"], rel))
            self.path_map[iid] = reg

        self._log(f"Archivos detectados en gdrive_import: {len(registros)}")

    def _seleccionar_credenciales(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar credenciales de servicio (JSON)",
            filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")],
            parent=self.win,
        )
        if ruta:
            self.cred_var.set(ruta)

    def _descargar_desde_drive(self, sobrescribir: bool):
        folder_id = self.folder_var.get().strip()
        if not folder_id:
            messagebox.showwarning("Google Drive", "Ingrese el ID de carpeta en Google Drive.", parent=self.win)
            return

        cred_path = os.path.expanduser(self.cred_var.get().strip())
        if not cred_path:
            messagebox.showwarning("Google Drive", "Seleccione el archivo de credenciales JSON.", parent=self.win)
            return
        if not os.path.exists(cred_path):
            messagebox.showerror("Error", f"No se encontró el archivo JSON:\n{cred_path}", parent=self.win)
            return

        if sobrescribir:
            confirmar = messagebox.askyesno(
                "Confirmar sobrescritura",
                "Se volverán a descargar y sobrescribir los archivos existentes en gdrive_import.\n¿Desea continuar?",
                parent=self.win,
            )
            if not confirmar:
                return

        self._log("Iniciando descarga desde Google Drive...")
        try:
            datasets = descargar_datasets_desde_drive(
                folder_id,
                cred_path,
                self._work_dir(),
                sobrescribir_existentes=sobrescribir,
                progress_cb=self._log,
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo descargar desde Google Drive:\n{e}", parent=self.win)
            self._log(f"Error en descarga: {e}")
            return

        total = sum(len(v) for v in datasets.values())
        self._log(f"Descarga finalizada. Archivos detectados en respuesta: {total}")
        self._recargar_tabla()

    def _seleccionar_por_categoria(self):
        categoria = self.categoria_var.get().strip()
        if not self.path_map:
            messagebox.showinfo("Google Drive", "No hay archivos para seleccionar en gdrive_import.", parent=self.win)
            return
        if not categoria or categoria == "Todas":
            self.tree.selection_set(self.tree.get_children())
            return

        seleccion = [iid for iid, reg in self.path_map.items() if reg["tipo"] == categoria]
        if not seleccion:
            messagebox.showinfo(
                "Google Drive",
                f"No se encontraron archivos para la categoría '{categoria}'.",
                parent=self.win,
            )
            return
        self.tree.selection_set(seleccion)

    def _cargar_seleccionados_al_master(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Google Drive", "Seleccione al menos un archivo para integrar al CSV master.", parent=self.win)
            return

        procesados = 0
        for iid in seleccion:
            reg = self.path_map.get(iid)
            if not reg:
                continue
            self.app.tipo_seleccionado.set(reg["tipo"])
            self.app.procesar_un_archivo(
                reg["ruta"],
                tipo_forzado=reg["tipo"],
                confirmar_encabezados=False,
                reemplazar_duplicados=True,
            )
            procesados += 1
            self.app.root.update_idletasks()

        self.app.actualizar_info()
        self._log(f"Integración finalizada. Archivos procesados: {procesados}")
        messagebox.showinfo("Google Drive", f"Se integraron {procesados} archivo(s) al CSV master.", parent=self.win)
