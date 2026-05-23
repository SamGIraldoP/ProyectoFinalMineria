import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os
import re
import unicodedata

# ================== Funciones de similitud ==================
def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])

def limpiar_texto_para_match(texto: str) -> str:
    texto = texto.lower()
    texto = quitar_acentos(texto)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def levenshtein_ratio(s1: str, s2: str) -> float:
    if not s1 and not s2: return 1.0
    if not s1 or not s2: return 0.0
    m, n = len(s1), len(s2)
    d = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): d[i][0] = i
    for j in range(n+1): d[0][j] = j
    for i in range(1, m+1):
        for j in range(1, n+1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            d[i][j] = min(d[i-1][j]+1, d[i][j-1]+1, d[i-1][j-1]+cost)
    return 1 - d[m][n] / max(m, n)


class VentanaPreprocesamiento:
    _PATRONES_MASCULINO = [
        "masculino", "hombre", "male", "varon", "masc", "m", "h",
        "masculino (hombre)", "hombre (masculino)"
    ]
    _PATRONES_FEMENINO = [
        "femenino", "mujer", "female", "fem", "f", "w", "muj",
        "femenino (mujer)", "mujer (femenino)"
    ]

    def __init__(self, parent, tipo, csv_path, app=None):
        self.parent = parent
        self.tipo = tipo
        self.csv_path = csv_path
        self.app = app
        self.df = None

        self.win = tk.Toplevel(parent)
        self.win.title(f"Preprocesamiento - {tipo}")
        self.win.configure(bg='white')
        self.win.resizable(True, True)
        self.win.minsize(600, 400)
        self.win.state('zoomed')

        self._crear_interfaz()
        self._cargar_datos()

    def _crear_interfaz(self):
        toolbar = ttk.Frame(self.win, padding=10)
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text=f"Archivo: {os.path.basename(self.csv_path)}",
                  font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="Quitar filas vacías",
                   command=self.quitar_filas_vacias, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Convertir tipos",
                   command=self.convertir_tipos, style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Label(toolbar, text="Ámbito:").pack(side=tk.LEFT, padx=5)
        self.año_seleccionado = tk.StringVar(value="Todos")
        self.cb_años = ttk.Combobox(toolbar, textvariable=self.año_seleccionado,
                                    state='readonly', width=8, font=('Segoe UI', 10))
        self.cb_años.pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="Aplicar limpieza al ámbito",
                   command=self.aplicar_limpieza_ambito, style='Accent.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(toolbar, text="Normalizar sexo/género",
                   command=self.normalizar_sexo_ambito, style='Accent.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(toolbar, text="🔎 Detectar inconsistencias (ámbito)",
                   command=self.detectar_inconsistencias, style='Warning.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="💾 Guardar cambios en CSV maestro",
                   command=self.guardar_en_maestro, style='Success.TButton').pack(side=tk.LEFT, padx=5)

        tree_frame = ttk.Frame(self.win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(tree_frame, show='headings')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Listo para comenzar el preprocesamiento.")
        status_frame = tk.Frame(self.win, bg='#2c3e50', height=30)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(status_frame, textvariable=self.status_var,
                                     bg='#2c3e50', fg='white', font=('Segoe UI', 9),
                                     anchor='w', padx=10)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _cargar_datos(self):
        self.status_var.set("Cargando datos del CSV maestro...")
        try:
            self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
            self._actualizar_vista()
            self._actualizar_combobox_años()
            self.status_var.set(f"Datos cargados: {len(self.df)} filas, {len(self.df.columns)} columnas.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el CSV:\n{e}")
            self.win.destroy()

    def _actualizar_vista(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if self.df is None or self.df.empty:
            return
        self.tree['columns'] = list(self.df.columns)
        for col in self.df.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        for i, (_, row) in enumerate(self.df.head(200).iterrows()):
            self.tree.insert('', 'end', values=list(row))

    def _actualizar_combobox_años(self):
        if self.df is None or 'Año' not in self.df.columns:
            self.cb_años['values'] = ["Todos"]
            self.año_seleccionado.set("Todos")
            return
        años = sorted(self.df['Año'].dropna().unique())
        años_int = []
        for a in años:
            try:
                años_int.append(int(float(a)))
            except:
                pass
        self.cb_años['values'] = ["Todos"] + años_int
        self.año_seleccionado.set("Todos")

    def _obtener_subconjunto(self):
        if self.df is None:
            return None, None
        seleccion = self.año_seleccionado.get()
        if seleccion == "Todos":
            return self.df, None
        try:
            año = int(seleccion)
        except ValueError:
            messagebox.showerror("Error", "Año inválido.")
            return None, None
        mask = self.df['Año'].astype(int) == año
        return self.df[mask], mask

    # ---------- Transformaciones ----------
    def quitar_filas_vacias(self):
        if self.df is None: return
        self.status_var.set("Eliminando filas completamente vacías (todo el dataset)...")
        antes = len(self.df)
        self.df.dropna(how='all', inplace=True)
        self._actualizar_vista()
        self.status_var.set(f"Filas vacías eliminadas: {antes - len(self.df)} (total ahora: {len(self.df)})")

    @staticmethod
    def _normalizar_texto(texto):
        if pd.isna(texto) or texto == '': return texto
        texto = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
        texto = texto.upper().strip()
        texto = re.sub(r'\s+', ' ', texto)
        return texto

    def _normalizar_instituciones(self, df):
        cols_ies = [col for col in df.columns if 'institucion' in col.lower()]
        for col in cols_ies:
            df[col] = df[col].apply(self._normalizar_texto)
        return df

    # ---------- Normalización de sexo/género ----------
    def _mapear_sexo(self, valor):
        limpio = limpiar_texto_para_match(valor)
        if not limpio:
            return valor
        mejor_sim_m = max((levenshtein_ratio(limpio, limpiar_texto_para_match(p)), p) for p in self._PATRONES_MASCULINO)
        mejor_sim_f = max((levenshtein_ratio(limpio, limpiar_texto_para_match(p)), p) for p in self._PATRONES_FEMENINO)
        umbral_sexo = 0.7
        if mejor_sim_m[0] >= umbral_sexo and mejor_sim_m[0] > mejor_sim_f[0]:
            return "Masculino"
        if mejor_sim_f[0] >= umbral_sexo and mejor_sim_f[0] > mejor_sim_m[0]:
            return "Femenino"
        return valor

    def _normalizar_sexo_df(self, df):
        cols_sexo = [col for col in df.columns if any(p in col.lower() for p in ['sexo', 'genero'])]
        for col in cols_sexo:
            df[col] = df[col].apply(lambda x: self._mapear_sexo(x) if pd.notna(x) and x != '' else x)
        return df

    def normalizar_sexo_ambito(self):
        if self.df is None: return
        seleccion = self.año_seleccionado.get()
        msg = "Se normalizarán los valores de sexo/género en el ámbito seleccionado."
        if not messagebox.askyesno("Normalizar sexo/género", msg):
            return
        sub, mask = self._obtener_subconjunto()
        if sub is None or sub.empty:
            messagebox.showwarning("Sin datos", "No hay datos para el ámbito seleccionado.")
            return
        self.status_var.set("Normalizando sexo/género...")
        sub = self._normalizar_sexo_df(sub)
        if mask is not None:
            self.df.loc[mask] = sub
        else:
            self.df = sub
        self._actualizar_vista()
        self.status_var.set("Normalización de sexo/género completada.")

    # ---------- Conversión de tipos ----------
    def _convertir_tipos_df(self, df):
        if 'Año' in df.columns:
            df['Año'] = pd.to_numeric(df['Año'], errors='coerce').fillna(0).astype(int)
        candidatas = ['Total', 'Auxiliar', 'Técnico', 'Profesional', 'Directivo',
                      'ADMITIDOS', 'GRADUADOS', 'INSCRITOS', 'Matriculados 2017',
                      'No. de Docentes', 'PRIMER CURSO']
        for col in candidatas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df

    def convertir_tipos(self):
        if self.df is None: return
        self.status_var.set("Convirtiendo tipos de datos (todo el dataset)...")
        self._convertir_tipos_df(self.df)
        self._actualizar_vista()
        self.status_var.set("Conversión de tipos finalizada.")

    # ---------- Aplicar limpieza al ámbito ----------
    def aplicar_limpieza_ambito(self):
        if self.df is None: return
        seleccion = self.año_seleccionado.get()
        if seleccion == "Todos":
            msg = "Se aplicarán las operaciones de limpieza a TODO el dataset."
        else:
            msg = f"Se aplicarán las operaciones de limpieza solo al año {seleccion}."
        if not messagebox.askyesno("Confirmar ámbito", msg + "\n¿Continuar?"):
            return

        sub, mask = self._obtener_subconjunto()
        if sub is None or sub.empty:
            messagebox.showwarning("Sin datos", "No hay datos para el ámbito seleccionado.")
            return

        self.status_var.set(f"Aplicando limpieza al ámbito {seleccion}...")
        antes = len(sub)
        sub.dropna(how='all', inplace=True)
        sub = self._normalizar_instituciones(sub)
        sub = self._normalizar_sexo_df(sub)
        sub = self._convertir_tipos_df(sub)

        if mask is not None:
            self.df.loc[mask] = sub
            self.df = self.df.dropna(how='all')
        else:
            self.df = sub

        self._actualizar_vista()
        self.status_var.set(f"Limpieza aplicada al ámbito {seleccion}. Filas eliminadas: {antes - len(sub)}")

    # ---------- Detección de inconsistencias ----------
    def detectar_inconsistencias(self):
        if self.df is None: return
        sub, _ = self._obtener_subconjunto()
        if sub is None or sub.empty:
            messagebox.showwarning("Sin datos", "No hay datos en el ámbito seleccionado.")
            return

        seleccion = self.año_seleccionado.get()
        self.status_var.set(f"Analizando columnas para detectar inconsistencias (ámbito: {seleccion})...")

        columnas_nombres = [col for col in sub.columns if any(palabra in col.lower() for palabra in
                            ['institución', 'institucion', 'ies', 'municipio', 'departamento',
                             'programa', 'metodología', 'metodologia', 'área', 'area', 'núcleo', 'nucleo'])]
        if not columnas_nombres:
            messagebox.showinfo("Sin columnas objetivo", "No se encontraron columnas de nombres relevantes.")
            self.status_var.set("Listo.")
            return

        umbral = 0.85
        reporte = []
        for col in columnas_nombres:
            n_unicos = sub[col].nunique()
            if n_unicos > 1000:
                continue
            conteo = sub[col].value_counts()
            top_nombres = conteo.head(200).index.tolist()
            if len(top_nombres) < 2:
                continue
            grupos = {}
            for nombre in top_nombres:
                nombre_limpio = limpiar_texto_para_match(nombre)
                asignado = False
                for clave, grupo in grupos.items():
                    if levenshtein_ratio(nombre_limpio, clave) >= umbral:
                        grupo.append(nombre)
                        asignado = True
                        break
                if not asignado:
                    grupos[nombre_limpio] = [nombre]
            for clave, variantes in grupos.items():
                if len(variantes) > 1:
                    canonico = max(variantes, key=lambda x: conteo[x])
                    for var in variantes:
                        if var != canonico:
                            reporte.append({
                                'columna': col,
                                'valor_actual': var,
                                'valor_canonico': canonico,
                                'frecuencia_actual': conteo[var],
                                'frecuencia_canonico': conteo[canonico]
                            })
        if not reporte:
            messagebox.showinfo("Sin inconsistencias", "No se detectaron variaciones significativas en los nombres.")
            self.status_var.set("No se encontraron inconsistencias.")
            return
        self._mostrar_reporte_inconsistencias(reporte, sub)

    def _mostrar_reporte_inconsistencias(self, reporte, sub_df):
        ventana_reporte = tk.Toplevel(self.win)
        ventana_reporte.title("Inconsistencias detectadas")
        ventana_reporte.geometry("900x600")
        ventana_reporte.configure(bg='white')
        ventana_reporte.resizable(True, True)

        style = ttk.Style()
        style.configure("Incon.Treeview", rowheight=24, borderwidth=1, relief="solid")
        style.map("Incon.Treeview", background=[('selected', '#3498db')])

        top_frame = ttk.Frame(ventana_reporte, padding=10)
        top_frame.pack(fill=tk.X)

        tk.Label(top_frame, text="Filtrar por columna:", bg='white').pack(side=tk.LEFT, padx=5)
        self.filtro_columna_var = tk.StringVar(value="Todas")
        columnas_unicas = sorted(list({r['columna'] for r in reporte}))
        cmb_filtro = ttk.Combobox(top_frame, textvariable=self.filtro_columna_var,
                                  values=["Todas"] + columnas_unicas, state='readonly', width=30)
        cmb_filtro.pack(side=tk.LEFT, padx=5)
        cmb_filtro.bind('<<ComboboxSelected>>', lambda e: self._refrescar_tabla_inconsistencias())

        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(top_frame, text="Seleccionar visibles",
                   command=lambda: self._marcar_todas(True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Deseleccionar visibles",
                   command=lambda: self._marcar_todas(False)).pack(side=tk.LEFT, padx=5)

        self.tree_inconsistencias = ttk.Treeview(ventana_reporte,
                                                 columns=('Seleccionar', 'Invertir', 'columna', 'actual', 'frec_actual',
                                                          'canonico', 'frec_canonico'),
                                                 show='headings', selectmode='none',
                                                 style="Incon.Treeview")
        self.tree_inconsistencias.heading('Seleccionar', text='✔')
        self.tree_inconsistencias.column('Seleccionar', width=30, anchor='center')
        self.tree_inconsistencias.heading('Invertir', text='↔')
        self.tree_inconsistencias.column('Invertir', width=30, anchor='center')
        self.tree_inconsistencias.heading('columna', text='Columna',
                                          command=lambda: self._ordenar_por('columna'))
        self.tree_inconsistencias.column('columna', width=150)
        self.tree_inconsistencias.heading('actual', text='Valor actual',
                                          command=lambda: self._ordenar_por('valor_actual'))
        self.tree_inconsistencias.column('actual', width=250)
        self.tree_inconsistencias.heading('frec_actual', text='Frec. actual',
                                          command=lambda: self._ordenar_por('frecuencia_actual'))
        self.tree_inconsistencias.column('frec_actual', width=100, anchor='e')
        self.tree_inconsistencias.heading('canonico', text='Valor canónico',
                                          command=lambda: self._ordenar_por('valor_canonico'))
        self.tree_inconsistencias.column('canonico', width=250)
        self.tree_inconsistencias.heading('frec_canonico', text='Frec. canónica',
                                          command=lambda: self._ordenar_por('frecuencia_canonico'))
        self.tree_inconsistencias.column('frec_canonico', width=100, anchor='e')

        scrollbar_y = ttk.Scrollbar(ventana_reporte, orient='vertical', command=self.tree_inconsistencias.yview)
        self.tree_inconsistencias.configure(yscrollcommand=scrollbar_y.set)

        self.tree_inconsistencias.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y, padx=0, pady=5)

        self.tree_inconsistencias.bind('<Button-1>', self._toggle_checkbox)

        bottom_frame = ttk.Frame(ventana_reporte, padding=10)
        bottom_frame.pack(fill=tk.X)

        def aplicar_y_cerrar():
            seleccionados = [i for i, estado in enumerate(self.estados_checkboxes) if estado]
            if not seleccionados:
                messagebox.showinfo("Sin selección", "No ha marcado ninguna variación.")
                return
            for idx in seleccionados:
                r = reporte[idx]
                col = r['columna']
                if self.invertir_checkboxes[idx]:
                    mask = sub_df[col] == r['valor_canonico']
                    sub_df.loc[mask, col] = r['valor_actual']
                else:
                    mask = sub_df[col] == r['valor_actual']
                    sub_df.loc[mask, col] = r['valor_canonico']
            if self.año_seleccionado.get() != "Todos":
                mask_orig = self.df['Año'].astype(int) == int(self.año_seleccionado.get())
                self.df.loc[mask_orig] = sub_df
            else:
                self.df = sub_df
            messagebox.showinfo("Correcciones aplicadas", f"Se unificaron {len(seleccionados)} variaciones.")
            self._actualizar_vista()
            self.status_var.set("Inconsistencias de nombres corregidas (selección manual).")
            ventana_reporte.destroy()

        ttk.Button(bottom_frame, text="Aplicar correcciones seleccionadas",
                   command=aplicar_y_cerrar,
                   style='Primary.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(bottom_frame, text="Cerrar sin aplicar",
                   command=ventana_reporte.destroy).pack(side=tk.LEFT, padx=10)

        self.reporte_completo = reporte
        self.estados_checkboxes = [True] * len(reporte)
        self.invertir_checkboxes = [False] * len(reporte)
        self.orden_actual = ('columna', False)
        self._refrescar_tabla_inconsistencias()

    # ---------- Métodos para la tabla de inconsistencias ----------
    def _toggle_checkbox(self, event):
        region = self.tree_inconsistencias.identify_region(event.x, event.y)
        if region != 'cell': return
        col_id = self.tree_inconsistencias.identify_column(event.x)
        if col_id not in ('#1', '#2'): return
        item = self.tree_inconsistencias.identify_row(event.y)
        if not item: return
        idx = self.tree_inconsistencias.index(item)
        items_filtrados = self.tree_inconsistencias.get_children()
        if idx < len(items_filtrados):
            item_id = items_filtrados[idx]
            valores = self.tree_inconsistencias.item(item_id)['values']
            if valores:
                col_actual = valores[2]
                val_actual = valores[3]
                for i, r in enumerate(self.reporte_completo):
                    if r['columna'] == col_actual and r['valor_actual'] == val_actual:
                        if col_id == '#1':
                            self.estados_checkboxes[i] = not (valores[0] == '☑')
                        else:
                            self.invertir_checkboxes[i] = not (valores[1] == '☑')
                        break
                self._refrescar_tabla_inconsistencias()

    def _marcar_todas(self, estado):
        filtro = self.filtro_columna_var.get()
        for i, r in enumerate(self.reporte_completo):
            if filtro == "Todas" or r['columna'] == filtro:
                self.estados_checkboxes[i] = estado
        self._refrescar_tabla_inconsistencias()

    def _ordenar_por(self, campo):
        mapa = {'columna':'columna','valor_actual':'valor_actual','frecuencia_actual':'frecuencia_actual',
                'valor_canonico':'valor_canonico','frecuencia_canonico':'frecuencia_canonico'}
        clave = mapa.get(campo)
        if not clave: return
        descendente = False
        if self.orden_actual[0] == clave:
            descendente = not self.orden_actual[1]
        self.orden_actual = (clave, descendente)
        self.reporte_completo.sort(key=lambda x: x[clave], reverse=descendente)
        self._refrescar_tabla_inconsistencias()

    def _refrescar_tabla_inconsistencias(self):
        for item in self.tree_inconsistencias.get_children():
            self.tree_inconsistencias.delete(item)
        filtro = self.filtro_columna_var.get()
        color_par = '#f5f5f5'
        color_impar = 'white'
        row_count = 0
        for i, r in enumerate(self.reporte_completo):
            if filtro != "Todas" and r['columna'] != filtro:
                continue
            marca_sel = '☑' if self.estados_checkboxes[i] else '☐'
            marca_inv = '☑' if self.invertir_checkboxes[i] else '☐'
            color = color_par if row_count % 2 == 0 else color_impar
            self.tree_inconsistencias.insert('', 'end', iid=f"r{i}",
                                             values=(marca_sel, marca_inv, r['columna'], r['valor_actual'],
                                                     r['frecuencia_actual'], r['valor_canonico'],
                                                     r['frecuencia_canonico']),
                                             tags=(color,))
            row_count += 1
        self.tree_inconsistencias.tag_configure(color_par, background=color_par)
        self.tree_inconsistencias.tag_configure(color_impar, background=color_impar)

    def guardar_en_maestro(self):
        if self.df is None: return
        if not messagebox.askyesno("Confirmar", "¿Sobrescribir el archivo CSV maestro con los cambios realizados?"):
            return
        self.status_var.set("Guardando cambios en el archivo maestro...")
        try:
            self.df.to_csv(self.csv_path, index=False, encoding='utf-8-sig')
            messagebox.showinfo("Guardado", "Los cambios se han guardado en el archivo maestro.")
            self.status_var.set("Cambios guardados correctamente.")
            if self.app:
                self.app._cargar_datos_completos(self.tipo)
                self.app.actualizar_info()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            self.status_var.set("Error al guardar.")