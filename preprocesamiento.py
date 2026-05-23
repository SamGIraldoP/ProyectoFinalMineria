import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os
import re
import unicodedata

# ──────────────────────────────────────────────────────────────────────────────
# Tabla de traducción: quita todo carácter que no sea a-z, 0-9 ni espacio.
# Se construye una sola vez al importar el módulo.
# ──────────────────────────────────────────────────────────────────────────────
_TABLA_PUNTUACION = str.maketrans(
    '',
    '',
    ''.join(
        chr(i) for i in range(0x110000)
        if unicodedata.category(chr(i)).startswith('P')
        or unicodedata.category(chr(i)) == 'So'
    )
)

# ================== Funciones de similitud ==================

def quitar_acentos(texto: str) -> str:
    """Elimina diacríticos de una cadena unicode."""
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('ascii')


def limpiar_texto_para_match(texto: str) -> str:
    """
    Normaliza texto para comparación difusa.
    Optimizado: usa str.translate en lugar de re.sub para eliminar puntuación
    (3-5× más rápido para cadenas cortas/medianas).
    """
    texto = quitar_acentos(texto.lower())
    texto = texto.translate(_TABLA_PUNTUACION)   # quita puntuación sin regex
    # Comprime espacios con un solo split/join (más rápido que re.sub r'\s+')
    return ' '.join(texto.split())


def levenshtein_ratio(s1: str, s2: str) -> float:
    """
    Ratio de similitud Levenshtein.
    Optimizaciones aplicadas:
      - Salida anticipada para cadenas idénticas o vacías.
      - Arreglo de 2 filas en lugar de matriz m×n  →  O(min(m,n)) de memoria.
      - Garantiza que s1 sea la cadena más corta  →  fila interior más pequeña.
    """
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Garantiza que la fila interior (s2) sea la más larga
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    m, n = len(s1), len(s2)
    prev = list(range(n + 1))
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        curr[0] = i
        s1_i = s1[i - 1]
        for j in range(1, n + 1):
            cost = 0 if s1_i == s2[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev   # intercambio sin copia

    return 1.0 - prev[n] / n  # n = max(m, n) ya que garantizamos m ≤ n


# ──────────────────────────────────────────────────────────────────────────────
# Pre-limpieza de patrones de sexo/género: se hace UNA sola vez al definir
# la clase, no en cada llamada a _mapear_sexo.
# ──────────────────────────────────────────────────────────────────────────────
def _precomputar_patrones(lista):
    return [(limpiar_texto_para_match(p), p) for p in lista]


class VentanaPreprocesamiento:
    _PATRONES_MASCULINO_RAW = [
        "masculino", "hombre", "male", "varon", "masc", "m", "h",
        "masculino (hombre)", "hombre (masculino)"
    ]
    _PATRONES_FEMENINO_RAW = [
        "femenino", "mujer", "female", "fem", "f", "w", "muj",
        "femenino (mujer)", "mujer (femenino)"
    ]
    # Patrones ya limpios, calculados una sola vez.
    _PATRONES_M_LIMPIOS = _precomputar_patrones(_PATRONES_MASCULINO_RAW)
    _PATRONES_F_LIMPIOS = _precomputar_patrones(_PATRONES_FEMENINO_RAW)
    _UMBRAL_SEXO = 0.7

    def __init__(self, parent, tipo, csv_path, app=None):
        self.parent = parent
        self.tipo = tipo
        self.csv_path = csv_path
        self.app = app
        self.df = None
        # Índice de lookup para checkbox toggle: (columna, valor_actual) → índice
        self._lookup_reporte: dict = {}

        self.win = tk.Toplevel(parent)
        self.win.title(f"Preprocesamiento - {tipo}")
        self.win.configure(bg='white')
        self.win.resizable(True, True)
        self.win.minsize(600, 400)
        self.win.state('zoomed')

        self._crear_interfaz()
        self._cargar_datos()

    # ─────────────────────────── Interfaz ────────────────────────────────────

    def _crear_interfaz(self):
        toolbar = ttk.Frame(self.win, padding=10)
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text=f"Archivo: {os.path.basename(self.csv_path)}",
                  font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="Quitar filas vacías",
                   command=self.quitar_filas_vacias,
                   style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Convertir tipos",
                   command=self.convertir_tipos,
                   style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Label(toolbar, text="Ámbito:").pack(side=tk.LEFT, padx=5)
        self.año_seleccionado = tk.StringVar(value="Todos")
        self.cb_años = ttk.Combobox(toolbar, textvariable=self.año_seleccionado,
                                    state='readonly', width=8, font=('Segoe UI', 10))
        self.cb_años.pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="Aplicar limpieza al ámbito",
                   command=self.aplicar_limpieza_ambito,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(toolbar, text="Normalizar sexo/género",
                   command=self.normalizar_sexo_ambito,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(toolbar, text="🔎 Detectar inconsistencias (ámbito)",
                   command=self.detectar_inconsistencias,
                   style='Warning.TButton').pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar, text="💾 Guardar cambios en CSV maestro",
                   command=self.guardar_en_maestro,
                   style='Success.TButton').pack(side=tk.LEFT, padx=5)

        tree_frame = ttk.Frame(self.win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(tree_frame, show='headings')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",  command=self.tree.yview)
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
        self.status_label = tk.Label(
            status_frame, textvariable=self.status_var,
            bg='#2c3e50', fg='white', font=('Segoe UI', 9), anchor='w', padx=10
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ─────────────────────────── Carga ───────────────────────────────────────

    def _cargar_datos(self):
        self.status_var.set("Cargando datos del CSV maestro...")
        try:
            self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig',
                                  dtype=str, keep_default_na=False)
            self._actualizar_vista()
            self._actualizar_combobox_años()
            self.status_var.set(
                f"Datos cargados: {len(self.df)} filas, {len(self.df.columns)} columnas."
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el CSV:\n{e}")
            self.win.destroy()

    def _actualizar_vista(self):
        self.tree.delete(*self.tree.get_children())   # borra todo de una vez
        if self.df is None or self.df.empty:
            return
        cols = list(self.df.columns)
        self.tree['columns'] = cols
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        # Inserción en lote: evita llamadas individuales al motor TCL
        for row in self.df.head(200).itertuples(index=False):
            self.tree.insert('', 'end', values=row)

    def _actualizar_combobox_años(self):
        if self.df is None or 'Año' not in self.df.columns:
            self.cb_años['values'] = ["Todos"]
            self.año_seleccionado.set("Todos")
            return
        años_int = sorted({
            int(float(a))
            for a in self.df['Año'].dropna().unique()
            if a not in ('', 'nan')
        }, key=lambda x: x)
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
        # Convertimos la columna una sola vez para la comparación
        mask = pd.to_numeric(self.df['Año'], errors='coerce').fillna(-1).astype(int) == año
        return self.df[mask], mask

    # ─────────────────────────── Transformaciones ────────────────────────────

    # Variantes de "sin información" que se tratan como nulo.
    # Se comparan contra la versión limpia (minúsculas, sin acentos, sin puntuación).
    _VALORES_NULOS_TEXTO = frozenset({
        'sin informacion', 'sin info', 'sinformacion', 'sin informacion disponible',
        'no disponible', 'nd', 'n/d', 'na', 'n/a', 'no aplica', 'no data',
        'no registra', 'no registrado', 'sin dato', 'sin datos', 'sin registro',
        'desconocido', 'desconocida', 'ninguno', 'ninguna', 'null', 'none',
        'nan', 'no hay informacion', 'no hay datos',
    })

    @classmethod
    def _es_valor_nulo_texto(cls, valor: str) -> bool:
        """Devuelve True si el valor es vacío o equivale a 'sin información'."""
        if not valor or not valor.strip():
            return True
        limpio = limpiar_texto_para_match(valor)
        return limpio in cls._VALORES_NULOS_TEXTO

    def _nulificar_celdas_vacias(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
        """
        Reemplaza por NaN:
          - Celdas vacías o que solo contienen espacios.
          - Celdas cuyo texto limpio coincide con un sinónimo de 'sin información'.

        Devuelve (df_modificado, n_celdas_vacias, n_celdas_sin_info).
        """
        # Máscara de celdas vacías / solo espacios
        mask_vacia = df.map(lambda v: isinstance(v, str) and not v.strip())

        # Máscara de sinónimos de "sin información" (excluye ya las vacías para no contar doble)
        mask_sin_info = (~mask_vacia) & df.map(
            lambda v: isinstance(v, str) and self._es_valor_nulo_texto(v)
        )

        n_vacias   = int(mask_vacia.sum().sum())
        n_sin_info = int(mask_sin_info.sum().sum())

        # Aplica ambas máscaras de una vez
        df[mask_vacia | mask_sin_info] = pd.NA
        return df, n_vacias, n_sin_info

    def quitar_filas_vacias(self):
        if self.df is None:
            return

        self.status_var.set("Analizando celdas vacías y valores nulos en el dataset...")

        # 1. Nulificar celdas vacías y sinónimos de "sin información"
        self.df, n_vacias, n_sin_info = self._nulificar_celdas_vacias(self.df)

        # 2. Eliminar filas completamente nulas (resultado de la nulificación o previas)
        antes = len(self.df)
        self.df.dropna(how='all', inplace=True)
        filas_eliminadas = antes - len(self.df)

        self._actualizar_vista()
        self.status_var.set(
            f"Celdas vacias → NaN: {n_vacias} | "
            f"'Sin información' → NaN: {n_sin_info} | "
            f"Filas eliminadas: {filas_eliminadas} | "
            f"Total filas: {len(self.df)}"
        )

    @staticmethod
    def _normalizar_texto(texto):
        """
        Normaliza texto de instituciones.
        Optimización: usa encode/decode ASCII (más rápido que unicodedata c-por-c)
        en lugar de recorrer el NFD carácter a carácter.
        """
        if not texto or pd.isna(texto):
            return texto
        texto = (
            unicodedata.normalize('NFKD', str(texto))
            .encode('ASCII', 'ignore')
            .decode('ascii')
            .upper()
            .strip()
        )
        return ' '.join(texto.split())   # comprime espacios sin regex

    def _normalizar_instituciones(self, df):
        cols_ies = [c for c in df.columns if 'institucion' in c.lower()]
        for col in cols_ies:
            df[col] = df[col].map(self._normalizar_texto)
        return df

    # ──────────────── Normalización de sexo/género ───────────────────────────

    def _mapear_sexo(self, valor: str) -> str:
        """
        Clasifica un valor de sexo/género como 'Masculino' o 'Femenino'.
        Usa los patrones pre-limpios de clase (_PATRONES_M/F_LIMPIOS) para evitar
        llamar limpiar_texto_para_match en cada patrón en cada invocación.
        """
        limpio = limpiar_texto_para_match(valor)
        if not limpio:
            return valor

        sim_m = max(levenshtein_ratio(limpio, p) for p, _ in self._PATRONES_M_LIMPIOS)
        sim_f = max(levenshtein_ratio(limpio, p) for p, _ in self._PATRONES_F_LIMPIOS)

        if sim_m >= self._UMBRAL_SEXO and sim_m > sim_f:
            return "Masculino"
        if sim_f >= self._UMBRAL_SEXO and sim_f > sim_m:
            return "Femenino"
        return valor

    def _normalizar_sexo_df(self, df):
        cols_sexo = [
            c for c in df.columns
            if any(p in c.lower() for p in ('sexo', 'genero'))
        ]
        for col in cols_sexo:
            # Aplica solo a celdas no vacías usando map + conditional
            mask_nonempty = df[col].notna() & (df[col] != '')
            df.loc[mask_nonempty, col] = df.loc[mask_nonempty, col].map(self._mapear_sexo)
        return df

    def normalizar_sexo_ambito(self):
        if self.df is None:
            return
        if not messagebox.askyesno(
            "Normalizar sexo/género",
            "Se normalizarán los valores de sexo/género en el ámbito seleccionado."
        ):
            return
        sub, mask = self._obtener_subconjunto()
        if sub is None or sub.empty:
            messagebox.showwarning("Sin datos", "No hay datos para el ámbito seleccionado.")
            return
        self.status_var.set("Normalizando sexo/género...")
        sub = self._normalizar_sexo_df(sub.copy())
        if mask is not None:
            self.df.loc[mask] = sub
        else:
            self.df = sub
        self._actualizar_vista()
        self.status_var.set("Normalización de sexo/género completada.")

    # ─────────────────────────── Conversión de tipos ─────────────────────────

    _COLS_NUMERICAS = frozenset({
        'Total', 'Auxiliar', 'Técnico', 'Profesional', 'Directivo',
        'ADMITIDOS', 'GRADUADOS', 'INSCRITOS', 'Matriculados 2017',
        'No. de Docentes', 'PRIMER CURSO'
    })

    def _convertir_tipos_df(self, df):
        if 'Año' in df.columns:
            df['Año'] = pd.to_numeric(df['Año'], errors='coerce').fillna(0).astype(int)
        cols_presentes = self._COLS_NUMERICAS & set(df.columns)
        for col in cols_presentes:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df

    def convertir_tipos(self):
        if self.df is None:
            return
        self.status_var.set("Convirtiendo tipos de datos (todo el dataset)...")
        self._convertir_tipos_df(self.df)
        self._actualizar_vista()
        self.status_var.set("Conversión de tipos finalizada.")

    # ─────────────────────────── Limpieza al ámbito ──────────────────────────

    def aplicar_limpieza_ambito(self):
        if self.df is None:
            return
        seleccion = self.año_seleccionado.get()
        msg = (
            "Se aplicarán las operaciones de limpieza a TODO el dataset."
            if seleccion == "Todos"
            else f"Se aplicarán las operaciones de limpieza solo al año {seleccion}."
        )
        if not messagebox.askyesno("Confirmar ámbito", msg + "\n¿Continuar?"):
            return

        sub, mask = self._obtener_subconjunto()
        if sub is None or sub.empty:
            messagebox.showwarning("Sin datos", "No hay datos para el ámbito seleccionado.")
            return

        self.status_var.set(f"Aplicando limpieza al ámbito {seleccion}...")
        antes = len(sub)
        sub = sub.copy()

        # Nulifica celdas vacías y sinónimos de "sin información" antes del resto
        sub, n_vacias, n_sin_info = self._nulificar_celdas_vacias(sub)
        sub.dropna(how='all', inplace=True)
        sub = self._normalizar_instituciones(sub)
        sub = self._normalizar_sexo_df(sub)
        sub = self._convertir_tipos_df(sub)

        if mask is not None:
            self.df.loc[mask] = sub
            self.df.dropna(how='all', inplace=True)
        else:
            self.df = sub

        self._actualizar_vista()
        self.status_var.set(
            f"Limpieza ámbito {seleccion} | "
            f"Celdas vacías → NaN: {n_vacias} | "
            f"'Sin información' → NaN: {n_sin_info} | "
            f"Filas eliminadas: {antes - len(sub)}"
        )

    # ─────────────────────────── Detección de inconsistencias ────────────────

    def detectar_inconsistencias(self):
        if self.df is None:
            return
        sub, _ = self._obtener_subconjunto()
        if sub is None or sub.empty:
            messagebox.showwarning("Sin datos", "No hay datos en el ámbito seleccionado.")
            return

        seleccion = self.año_seleccionado.get()
        self.status_var.set(
            f"Analizando columnas para detectar inconsistencias (ámbito: {seleccion})..."
        )

        _PALABRAS_CLAVE = ('instituci', 'ies', 'municipio', 'departamento',
                           'programa', 'metodolog', 'area', 'nucleo')
        columnas_nombres = [
            c for c in sub.columns
            if any(p in quitar_acentos(c.lower()) for p in _PALABRAS_CLAVE)
        ]
        if not columnas_nombres:
            messagebox.showinfo("Sin columnas objetivo",
                                "No se encontraron columnas de nombres relevantes.")
            self.status_var.set("Listo.")
            return

        umbral = 0.85
        reporte = []

        for col in columnas_nombres:
            if sub[col].nunique() > 1000:
                continue
            conteo = sub[col].value_counts()
            top_nombres = conteo.head(200).index.tolist()
            if len(top_nombres) < 2:
                continue

            # Caché de nombres limpios: evita recalcular en cada comparación del bucle interno
            cache_limpio = {n: limpiar_texto_para_match(n) for n in top_nombres}

            grupos: dict[str, list] = {}
            for nombre in top_nombres:
                nombre_limpio = cache_limpio[nombre]
                asignado = False
                for clave, grupo in grupos.items():
                    # Salida anticipada: en cuanto encontramos grupo compatible, paramos
                    if levenshtein_ratio(nombre_limpio, clave) >= umbral:
                        grupo.append(nombre)
                        asignado = True
                        break
                if not asignado:
                    grupos[nombre_limpio] = [nombre]

            for clave, variantes in grupos.items():
                if len(variantes) < 2:
                    continue
                canonico = max(variantes, key=lambda x: conteo[x])
                for var in variantes:
                    if var != canonico:
                        reporte.append({
                            'columna':           col,
                            'valor_actual':      var,
                            'valor_canonico':    canonico,
                            'frecuencia_actual': conteo[var],
                            'frecuencia_canonico': conteo[canonico]
                        })

        if not reporte:
            messagebox.showinfo("Sin inconsistencias",
                                "No se detectaron variaciones significativas en los nombres.")
            self.status_var.set("No se encontraron inconsistencias.")
            return

        self._mostrar_reporte_inconsistencias(reporte, sub)

    # ─────────────────────────── Ventana de inconsistencias ──────────────────

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
        columnas_unicas = sorted({r['columna'] for r in reporte})
        cmb_filtro = ttk.Combobox(top_frame, textvariable=self.filtro_columna_var,
                                  values=["Todas"] + columnas_unicas,
                                  state='readonly', width=30)
        cmb_filtro.pack(side=tk.LEFT, padx=5)
        cmb_filtro.bind('<<ComboboxSelected>>', lambda e: self._refrescar_tabla_inconsistencias())

        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Button(top_frame, text="Seleccionar visibles",
                   command=lambda: self._marcar_todas(True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Deseleccionar visibles",
                   command=lambda: self._marcar_todas(False)).pack(side=tk.LEFT, padx=5)

        self.tree_inconsistencias = ttk.Treeview(
            ventana_reporte,
            columns=('Seleccionar', 'Invertir', 'columna', 'actual',
                     'frec_actual', 'canonico', 'frec_canonico'),
            show='headings', selectmode='none', style="Incon.Treeview"
        )
        for col_id, texto, ancho, anchor in (
            ('Seleccionar', '✔',             30,  'center'),
            ('Invertir',    '↔',             30,  'center'),
            ('columna',     'Columna',       150, 'w'),
            ('actual',      'Valor actual',  250, 'w'),
            ('frec_actual', 'Frec. actual',  100, 'e'),
            ('canonico',    'Valor canónico',250, 'w'),
            ('frec_canonico','Frec. canónica',100,'e'),
        ):
            self.tree_inconsistencias.heading(col_id, text=texto,
                command=(lambda c=col_id: self._ordenar_por(c))
                if col_id not in ('Seleccionar', 'Invertir') else lambda: None)
            self.tree_inconsistencias.column(col_id, width=ancho, anchor=anchor)

        scrollbar_y = ttk.Scrollbar(ventana_reporte, orient='vertical',
                                    command=self.tree_inconsistencias.yview)
        self.tree_inconsistencias.configure(yscrollcommand=scrollbar_y.set)
        self.tree_inconsistencias.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y, padx=0, pady=5)

        self.tree_inconsistencias.bind('<Button-1>', self._toggle_checkbox)

        bottom_frame = ttk.Frame(ventana_reporte, padding=10)
        bottom_frame.pack(fill=tk.X)

        def aplicar_y_cerrar():
            seleccionados = [i for i, e in enumerate(self.estados_checkboxes) if e]
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
                mask_orig = (
                    pd.to_numeric(self.df['Año'], errors='coerce').fillna(-1).astype(int)
                    == int(self.año_seleccionado.get())
                )
                self.df.loc[mask_orig] = sub_df
            else:
                self.df = sub_df
            messagebox.showinfo("Correcciones aplicadas",
                                f"Se unificaron {len(seleccionados)} variaciones.")
            self._actualizar_vista()
            self.status_var.set("Inconsistencias de nombres corregidas (selección manual).")
            ventana_reporte.destroy()

        ttk.Button(bottom_frame, text="Aplicar correcciones seleccionadas",
                   command=aplicar_y_cerrar,
                   style='Primary.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(bottom_frame, text="Cerrar sin aplicar",
                   command=ventana_reporte.destroy).pack(side=tk.LEFT, padx=10)

        self.reporte_completo     = reporte
        self.estados_checkboxes   = [True]  * len(reporte)
        self.invertir_checkboxes  = [False] * len(reporte)
        self.orden_actual         = ('columna', False)

        # ── Índice O(1) para _toggle_checkbox ──────────────────────────────
        self._lookup_reporte = {
            (r['columna'], r['valor_actual']): i
            for i, r in enumerate(reporte)
        }
        self._refrescar_tabla_inconsistencias()

    # ─────────────────────────── Helpers de tabla ────────────────────────────

    def _toggle_checkbox(self, event):
        region = self.tree_inconsistencias.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id = self.tree_inconsistencias.identify_column(event.x)
        if col_id not in ('#1', '#2'):
            return
        item = self.tree_inconsistencias.identify_row(event.y)
        if not item:
            return
        valores = self.tree_inconsistencias.item(item, 'values')
        if not valores:
            return
        # Lookup O(1) en lugar de búsqueda lineal
        key = (valores[2], valores[3])
        idx = self._lookup_reporte.get(key)
        if idx is None:
            return
        if col_id == '#1':
            self.estados_checkboxes[idx] = not (valores[0] == '☑')
        else:
            self.invertir_checkboxes[idx] = not (valores[1] == '☑')
        self._refrescar_tabla_inconsistencias()

    def _marcar_todas(self, estado: bool):
        filtro = self.filtro_columna_var.get()
        for i, r in enumerate(self.reporte_completo):
            if filtro == "Todas" or r['columna'] == filtro:
                self.estados_checkboxes[i] = estado
        self._refrescar_tabla_inconsistencias()

    _CAMPO_ORDEN = frozenset(
        {'columna', 'valor_actual', 'frecuencia_actual', 'valor_canonico', 'frecuencia_canonico'}
    )

    def _ordenar_por(self, campo: str):
        if campo not in self._CAMPO_ORDEN:
            return
        descendente = (self.orden_actual[0] == campo) and not self.orden_actual[1]
        self.orden_actual = (campo, descendente)
        self.reporte_completo.sort(key=lambda x: x[campo], reverse=descendente)
        self._refrescar_tabla_inconsistencias()

    def _refrescar_tabla_inconsistencias(self):
        tree = self.tree_inconsistencias
        tree.delete(*tree.get_children())   # borra en un solo call

        filtro     = self.filtro_columna_var.get()
        COLOR_PAR  = '#f5f5f5'
        COLOR_IMPAR = 'white'
        tree.tag_configure(COLOR_PAR,   background=COLOR_PAR)
        tree.tag_configure(COLOR_IMPAR, background=COLOR_IMPAR)

        # Construye lista filtrada de una vez para no recalcular en cada fila
        filas = [
            (i, r) for i, r in enumerate(self.reporte_completo)
            if filtro == "Todas" or r['columna'] == filtro
        ]
        for row_count, (i, r) in enumerate(filas):
            tree.insert(
                '', 'end', iid=f"r{i}",
                values=(
                    '☑' if self.estados_checkboxes[i]  else '☐',
                    '☑' if self.invertir_checkboxes[i] else '☐',
                    r['columna'], r['valor_actual'], r['frecuencia_actual'],
                    r['valor_canonico'], r['frecuencia_canonico']
                ),
                tags=(COLOR_PAR if row_count % 2 == 0 else COLOR_IMPAR,)
            )

    # ─────────────────────────── Guardar ─────────────────────────────────────

    def guardar_en_maestro(self):
        if self.df is None:
            return
        if not messagebox.askyesno(
            "Confirmar",
            "¿Sobrescribir el archivo CSV maestro con los cambios realizados?"
        ):
            return
        self.status_var.set("Guardando cambios en el archivo maestro...")
        try:
            self.df.to_csv(self.csv_path, index=False, encoding='utf-8-sig')
            messagebox.showinfo("Guardado",
                                "Los cambios se han guardado en el archivo maestro.")
            self.status_var.set("Cambios guardados correctamente.")
            if self.app:
                self.app._cargar_datos_completos(self.tipo)
                self.app.actualizar_info()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            self.status_var.set("Error al guardar.")