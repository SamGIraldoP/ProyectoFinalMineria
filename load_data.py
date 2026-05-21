import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os
import re
import unicodedata
import time
import datetime

# ================== Configuración ==================
UMBRAL = 0.6

# ================== Directorio de datos ==================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ================== Funciones de similitud ==================
def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)])

def limpiar_nombre_columna(nombre: str) -> str:
    n = nombre.replace('\n', ' ').strip()
    n = n.strip('"').strip("'")
    n = re.sub(r'\s+', ' ', n)
    return n

def normalizar_para_match(nombre: str) -> str:
    nombre = nombre.lower()
    nombre = quitar_acentos(nombre)
    nombre = re.sub(r'[^a-z0-9\s]', '', nombre)
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    return nombre

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

def similitud_combinada(cadena1: str, cadena2: str) -> float:
    s1 = normalizar_para_match(cadena1)
    s2 = normalizar_para_match(cadena2)
    lev = levenshtein_ratio(s1, s2)
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())
    if not tokens1 and not tokens2: jaccard = 1.0
    elif not tokens1 or not tokens2: jaccard = 0.0
    else: jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
    return max(lev, jaccard)

def mapear_columnas_expandible(canonicas, nuevas_raw, umbral=UMBRAL):
    nuevas_limpias = [limpiar_nombre_columna(c) for c in nuevas_raw]
    canonicas_limpias = [limpiar_nombre_columna(c) for c in canonicas]
    parejas = []
    for i, cn in enumerate(canonicas_limpias):
        for j, nn in enumerate(nuevas_limpias):
            sim = similitud_combinada(cn, nn)
            if sim >= umbral:
                parejas.append((sim, i, j))
    parejas.sort(key=lambda x: x[0], reverse=True)
    canonicas_asignadas = set()
    nuevas_asignadas = set()
    mapeo = {i: None for i in range(len(canonicas))}
    for sim, i, j in parejas:
        if i not in canonicas_asignadas and j not in nuevas_asignadas:
            mapeo[i] = j
            canonicas_asignadas.add(i)
            nuevas_asignadas.add(j)
    return mapeo

# ================== Tooltip simple ==================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind('<Enter>', self.show_tip)
        widget.bind('<Leave>', self.hide_tip)

    def show_tip(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 9), padx=5, pady=3)
        label.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# ================== Interfaz principal ==================
class SNIESConsolidador:
    FIXED_HEADERS = {
        "Administrativos": [
            "Código de la Institución", "IES PADRE", "Institución de Educación Superior (IES)",
            "Principal o Seccional", "Sector IES", "Carácter IES",
            "Código del departamento (IES)", "Departamento de domicilio de la IES",
            "Código del Municipio (IES)", "Municipio de domicilio de la IES",
            "Año", "Semestre", "Auxiliar", "Técnico", "Profesional", "Directivo", "Total"
        ],
        "Estudiantes admitidos": [
            "CÓDIGO DE LA INSTITUCIÓN", "IES_PADRE", "INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)",
            "PRINCIPAL O SECCIONAL", "SECTOR IES", "CARACTER IES",
            "CÓDIGO DEL DEPARTAMENTO (IES)", "DEPARTAMENTO DE DOMICILIO DE LA IES",
            "CÓDIGO DEL MUNICIPIO IES", "MUNICIPIO DE DOMICILIO DE LA IES",
            "CÓDIGO SNIES DEL PROGRAMA", "PROGRAMA ACADÉMICO",
            "NIVEL ACADÉMICO", "NIVEL DE FORMACIÓN", "METODOLOGÍA",
            "ÁREA DE CONOCIMIENTO", "NÚCLEO BÁSICO DEL CONOCIMIENTO (NBC)",
            "DESC CINE CAMPO AMPLIO", "DESC CINE CAMPO ESPECIFICO", "DESC CINE CODIGO DETALLADO",
            "CÓDIGO DEL DEPARTAMENTO (PROGRAMA)", "DEPARTAMENTO DE OFERTA DEL PROGRAMA",
            "CÓDIGO DEL MUNICIPIO (PROGRAMA)", "MUNICIPIO DE OFERTA DEL PROGRAMA",
            "SEXO", "AÑO", "SEMESTRE", "ADMITIDOS"
        ],
        "Estudiantes graduados": [
            "CÓDIGO DE LA INSTITUCIÓN", "IES_PADRE", "INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)",
            "PRINCIPAL O SECCIONAL", "SECTOR IES", "CARACTER IES",
            "CÓDIGO DEL DEPARTAMENTO (IES)", "DEPARTAMENTO DE DOMICILIO DE LA IES",
            "CÓDIGO DEL MUNICIPIO", "MUNICIPIO DE DOMICILIO DE LA IES",
            "CÓDIGO SNIES DEL PROGRAMA", "PROGRAMA ACADÉMICO",
            "NIVEL ACADÉMICO", "NIVEL DE FORMACIÓN", "METODOLOGÍA",
            "ÁREA DE CONOCIMIENTO", "NÚCLEO BÁSICO DEL CONOCIMIENTO (NBC)",
            "DESC CINE CAMPO AMPLIO", "DESC CINE CAMPO ESPECIFICO", "DESC CINE CODIGO DETALLADO",
            "CÓDIGO DEL DEPARTAMENTO (PROGRAMA)", "DEPARTAMENTO DE OFERTA DEL PROGRAMA",
            "CÓDIGO DEL MUNICIPIO (PROGRAMA)", "MUNICIPIO DE OFERTA DEL PROGRAMA",
            "SEXO", "AÑO", "SEMESTRE", "GRADUADOS"
        ],
        "Estudiantes inscritos": [
            "CÓDIGO DE LA INSTITUCIÓN", "IES_PADRE", "INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)",
            "PRINCIPAL O SECCIONAL", "SECTOR IES", "CARACTER IES",
            "CÓDIGO DEL DEPARTAMENTO (IES)", "DEPARTAMENTO DE DOMICILIO DE LA IES",
            "CÓDIGO DEL MUNICIPIO (IES)", "MUNICIPIO DE DOMICILIO DE LA IES",
            "CÓDIGO SNIES DEL PROGRAMA", "PROGRAMA ACADÉMICO",
            "NIVEL ACADÉMICO", "NIVEL DE FORMACIÓN", "METODOLOGÍA",
            "ÁREA DE CONOCIMIENTO", "NÚCLEO BÁSICO DEL CONOCIMIENTO (NBC)",
            "DESC CINE CAMPO AMPLIO", "DESC CINE CAMPO ESPECIFICO", "DESC CINE CODIGO DETALLADO",
            "CÓDIGO DEL DEPARTAMENTO (PROGRAMA)", "DEPARTAMENTO DE OFERTA DEL PROGRAMA",
            "CÓDIGO DEL MUNICIPIO (PROGRAMA)", "MUNICIPIO DE OFERTA DEL PROGRAMA",
            "SEXO", "AÑO", "SEMESTRE", "INSCRITOS"
        ],
        "Estudiantes matriculados": [
            "Código de la Institución", "IES PADRE", "Institución de Educación Superior (IES)",
            "Principal o Seccional", "Sector IES", "Caracter IES",
            "Código del departamento (IES)", "Departamento de domicilio de la IES",
            "Código del Municipio (IES)", "Municipio de domicilio de la IES",
            "Código SNIES del programa", "Programa Académico",
            "Nivel Académico", "Nivel de Formación", "Metodología",
            "Área de Conocimiento", "Núcleo Básico del Conocimiento (NBC)",
            "Código del Departamento (Programa)", "Departamento de oferta del programa",
            "Código del Municipio (Programa)", "Municipio de oferta del programa",
            "Sexo", "Año", "Semestre", "Matriculados 2017"
        ],
        "Estudiantes matriculados en primer curso": [
            "CÓDIGO DE LA INSTITUCIÓN", "IES_PADRE", "INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)",
            "PRINCIPAL O SECCIONAL", "SECTOR IES", "CARACTER IES",
            "CÓDIGO DEL DEPARTAMENTO (IES)", "DEPARTAMENTO DE DOMICILIO DE LA IES",
            "CÓDIGO DEL MUNICIPIO (IES)", "MUNICIPIO DE DOMICILIO DE LA IES",
            "CÓDIGO SNIES DEL PROGRAMA", "PROGRAMA ACADÉMICO",
            "NIVEL ACADÉMICO", "NIVEL DE FORMACIÓN", "METODOLOGÍA",
            "ÁREA DE CONOCIMIENTO", "NÚCLEO BÁSICO DEL CONOCIMIENTO (NBC)",
            "DESC CINE CAMPO AMPLIO", "DESC CINE CAMPO ESPECIFICO", "DESC CINE CODIGO DETALLADO",
            "CÓDIGO DEL DEPARTAMENTO (PROGRAMA)", "DEPARTAMENTO DE OFERTA DEL PROGRAMA",
            "CÓDIGO DEL MUNICIPIO (PROGRAMA)", "MUNICIPIO DE OFERTA DEL PROGRAMA",
            "SEXO", "AÑO", "SEMESTRE", "PRIMER CURSO"
        ],
        "Docentes": [
            "Código de la Institución", "IES PADRE", "Institución de Educación Superior (IES)",
            "Principal o Seccional", "Sector IES", "Caracter IES",
            "Código del departamento (IES)", "Departamento de domicilio de la IES",
            "Código del Municipio (IES)", "Municipio de domicilio de la IES",
            "Sexo del Docente", "Máximo nivel de formación del docente",
            "Tiempo de dedicación del Docente", "Tipo de contrato del Docente",
            "Año", "Semestre", "No. de Docentes"
        ]
    }

    COLOR_PRIMARY = "#2c3e50"
    COLOR_SECONDARY = "#3498db"
    COLOR_ACCENT = "#1abc9c"
    COLOR_BG = "#ecf0f1"
    COLOR_TEXT = "#2c3e50"
    COLOR_SUCCESS = "#27ae60"
    COLOR_WARNING = "#f39c12"
    COLOR_DANGER = "#e74c3c"

    def __init__(self, root):
        self.root = root
        self.root.title("📊 Consolidador SNIES – Gestión de datasets")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.configure(bg=self.COLOR_BG)

        self.data = {}          # tipo -> {"headers": [...], "datasets": [...]}
        self.tipos = [
            "Estudiantes admitidos", "Estudiantes inscritos", "Estudiantes matriculados",
            "Estudiantes matriculados en primer curso", "Estudiantes graduados",
            "Docentes", "Administrativos"
        ]
        self.tipo_seleccionado = tk.StringVar()
        self.status_var = tk.StringVar(value="Listo para comenzar.")
        self.progress_var = tk.DoubleVar()

        self.configurar_estilos()
        self.crear_menu()
        self.crear_interfaz()
        self.cargar_csvs_existentes()      # solo metadatos
        self.actualizar_info()

    def configurar_estilos(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background=self.COLOR_BG, foreground=self.COLOR_TEXT, font=('Segoe UI', 10))
        style.configure('TFrame', background=self.COLOR_BG)
        style.configure('TLabel', background=self.COLOR_BG, font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10, 'bold'), borderwidth=0, focusthickness=0)
        style.map('TButton',
                  background=[('active', self.COLOR_PRIMARY), ('pressed', self.COLOR_SECONDARY)],
                  foreground=[('active', 'white')])
        style.configure('Primary.TButton', background=self.COLOR_PRIMARY, foreground='white')
        style.configure('Success.TButton', background=self.COLOR_SUCCESS, foreground='white')
        style.configure('Warning.TButton', background=self.COLOR_WARNING, foreground='white')
        style.configure('Danger.TButton', background=self.COLOR_DANGER, foreground='white')
        style.configure('Accent.TButton', background=self.COLOR_ACCENT, foreground='white')
        style.configure('Card.TFrame', background='white', relief='solid', borderwidth=1)
        style.configure('Card.TLabel', background='white', font=('Segoe UI', 10))
        style.configure('TCombobox', fieldbackground='white', background='white')
        style.configure('TEntry', fieldbackground='white')
        style.configure('TProgressbar', thickness=10)

    def crear_menu(self):
        menubar = tk.Menu(self.root, bg=self.COLOR_PRIMARY, fg='white', activebackground=self.COLOR_SECONDARY)
        self.root.config(menu=menubar)
        archivo_menu = tk.Menu(menubar, tearoff=0, bg='white', fg=self.COLOR_TEXT)
        archivo_menu.add_command(label="📂 Cargar Excel(s)", command=self.cargar_archivos)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="🧹 Limpiar todo el tipo", command=self.limpiar_datos)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="🚪 Salir", command=self.root.quit)
        menubar.add_cascade(label="Archivo", menu=archivo_menu)
        ayuda_menu = tk.Menu(menubar, tearoff=0, bg='white', fg=self.COLOR_TEXT)
        ayuda_menu.add_command(label="ℹ️ Acerca de", command=self.mostrar_acerca)
        menubar.add_cascade(label="Ayuda", menu=ayuda_menu)

    def crear_interfaz(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        titulo = ttk.Label(main_frame, text="Consolidador de Datos SNIES",
                           font=('Segoe UI', 18, 'bold'), foreground=self.COLOR_PRIMARY)
        titulo.grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky='w')

        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky='nsew', padx=(0, 10))
        main_frame.columnconfigure(1, weight=1)

        tipo_card = ttk.Frame(left_frame, style='Card.TFrame', padding=15)
        tipo_card.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(tipo_card, text="📋 Tipo de dataset:", font=('Segoe UI', 10, 'bold'),
                  background='white').pack(anchor='w')
        self.cb_tipo = ttk.Combobox(tipo_card, textvariable=self.tipo_seleccionado,
                                    values=self.tipos, state='readonly', width=38)
        self.cb_tipo.pack(fill=tk.X, pady=(5, 0))
        self.cb_tipo.set(self.tipos[0])
        self.cb_tipo.bind('<<ComboboxSelected>>', lambda e: self.actualizar_info())

        acciones_card = ttk.Frame(left_frame, style='Card.TFrame', padding=15)
        acciones_card.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(acciones_card, text="⚡ Acciones", font=('Segoe UI', 10, 'bold'),
                  background='white').pack(anchor='w', pady=(0, 8))

        btn_cargar = ttk.Button(acciones_card, text="📂 Cargar Excel(s)", command=self.cargar_archivos, style='Primary.TButton')
        btn_cargar.pack(fill=tk.X, pady=2)
        ToolTip(btn_cargar, "Selecciona uno o varios archivos Excel para cargar")

        btn_limpiar = ttk.Button(acciones_card, text="🧹 Limpiar todo", command=self.limpiar_datos, style='Warning.TButton')
        btn_limpiar.pack(fill=tk.X, pady=2)
        ToolTip(btn_limpiar, "Elimina todos los datasets del tipo actual y borra el CSV asociado")

        btn_encabezados = ttk.Button(acciones_card, text="🔍 Ver encabezados", command=self.ver_encabezados, style='Accent.TButton')
        btn_encabezados.pack(fill=tk.X, pady=2)
        ToolTip(btn_encabezados, "Muestra los nombres de columna esperados para este tipo")

        # Panel derecho (datasets + resumen)
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky='nsew')

        self.info_card = ttk.Frame(right_frame, style='Card.TFrame', padding=10)
        self.info_card.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.info_card, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.info_card, orient='vertical', command=self.canvas.yview)
        self.scroll_frame = ttk.Frame(self.canvas, style='Card.TFrame')

        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.progress = ttk.Progressbar(right_frame, variable=self.progress_var, maximum=100, style='TProgressbar')
        self.progress.pack(fill=tk.X, pady=(10, 0))

        # Resumen del tipo seleccionado
        self.resumen_frame = ttk.Frame(right_frame, style='Card.TFrame', padding=5)
        self.resumen_frame.pack(fill=tk.X, pady=(5, 0))
        self.lbl_resumen = ttk.Label(self.resumen_frame, text="", background='white',
                                     font=('Segoe UI', 10, 'bold'), foreground=self.COLOR_PRIMARY)
        self.lbl_resumen.pack()

        # Barra de estado
        status_frame = tk.Frame(self.root, bg=self.COLOR_PRIMARY, height=30)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(status_frame, textvariable=self.status_var, bg=self.COLOR_PRIMARY, fg='white',
                                     font=('Segoe UI', 9), anchor='w', padx=10)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    # ---------- Metadatos ----------
    @staticmethod
    def _metadata_path():
        return os.path.join(DATA_DIR, "metadata.csv")

    def _actualizar_metadatos(self, tipo, datasets):
        """Guarda en metadata.csv los años y registros de cada tipo."""
        md_path = self._metadata_path()
        # Leer existentes o crear nuevo
        if os.path.exists(md_path):
            df_md = pd.read_csv(md_path, dtype=str, keep_default_na=False)
        else:
            df_md = pd.DataFrame(columns=["tipo", "año", "registros"])
        # Eliminar entradas anteriores de este tipo
        df_md = df_md[df_md["tipo"] != tipo]
        # Agregar nuevas filas
        nuevas_filas = []
        for ds in datasets:
            nuevas_filas.append({"tipo": tipo, "año": str(ds["año"]), "registros": len(ds["filas"])})
        if nuevas_filas:
            df_new = pd.DataFrame(nuevas_filas)
            df_md = pd.concat([df_md, df_new], ignore_index=True)
        if df_md.empty:
            if os.path.exists(md_path):
                os.remove(md_path)
        else:
            df_md.to_csv(md_path, index=False, encoding="utf-8-sig")

    # ---------- Carga bajo demanda ----------
    def _cargar_datos_completos(self, tipo):
        """Carga el CSV completo del tipo si aún no está en memoria."""
        if tipo in self.data and self.data[tipo].get("datasets") and self.data[tipo]["datasets"][0].get("filas"):
            # ya están cargados los datos reales
            return
        path = self._csv_path(tipo)
        if not os.path.exists(path):
            return
        try:
            df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
            if df.empty:
                return
            canonicas = self.obtener_canonicas(tipo)
            if canonicas is None:
                canonicas = list(df.columns)
            self.data[tipo] = {"headers": canonicas, "datasets": []}
            if "Año" not in df.columns:
                return
            df["Año"] = pd.to_numeric(df["Año"], errors='coerce').fillna(0).astype(int)
            df = df[df["Año"] != 0]
            for año in sorted(df["Año"].unique()):
                subdf = df[df["Año"] == año]
                alineado = pd.DataFrame(columns=canonicas)
                for col in canonicas:
                    if col in subdf.columns:
                        alineado[col] = subdf[col].values
                    else:
                        alineado[col] = ""
                filas = alineado.values.tolist()
                n_cols = len(canonicas)
                for i in range(len(filas)):
                    if len(filas[i]) < n_cols:
                        filas[i] += [""] * (n_cols - len(filas[i]))
                    elif len(filas[i]) > n_cols:
                        filas[i] = filas[i][:n_cols]
                self.data[tipo]["datasets"].append({
                    "archivo": path,
                    "año": int(año),
                    "fila_inicio": None,
                    "filas": filas
                })
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los datos de {tipo}:\n{e}")

    # ---------- Carga inicial (solo metadatos) ----------
    def cargar_csvs_existentes(self):
        """Al iniciar, solo carga la información resumida de los metadatos."""
        md_path = self._metadata_path()
        if not os.path.exists(md_path):
            return
        try:
            df_md = pd.read_csv(md_path, dtype=str)
            for _, fila in df_md.iterrows():
                tipo = fila["tipo"]
                año = int(fila["año"])
                registros = int(fila["registros"])
                # Si el tipo no tiene estructura, la creamos vacía
                if tipo not in self.data:
                    canonicas = self.obtener_canonicas(tipo)
                    if canonicas is None:
                        canonicas = []   # se definirán al cargar completos
                    self.data[tipo] = {"headers": canonicas, "datasets": []}
                # Añadir dataset ligero (sin filas reales)
                self.data[tipo]["datasets"].append({
                    "archivo": self._csv_path(tipo),
                    "año": año,
                    "fila_inicio": None,
                    "filas": []   # vacío, los datos se cargan bajo demanda
                })
                # Guardamos el conteo en un atributo temporal para mostrarlo
                # (lo guardamos en el dataset con un campo extra "registros")
                self.data[tipo]["datasets"][-1]["registros"] = registros
            self.status_var.set("Metadatos cargados correctamente.")
        except Exception as e:
            print(f"Error al leer metadatos: {e}")

    def _csv_path(self, tipo):
        nombre_archivo = tipo.replace(" ", "_") + ".csv"
        return os.path.join(DATA_DIR, nombre_archivo)

    def _actualizar_csv(self, tipo):
        """Guarda el CSV del tipo y actualiza los metadatos."""
        path = self._csv_path(tipo)
        if tipo not in self.data or not self.data[tipo]["datasets"]:
            if os.path.exists(path):
                os.remove(path)
            self._actualizar_metadatos(tipo, [])
            return
        headers = self.data[tipo]["headers"]
        n_cols = len(headers)
        todas_filas = []
        for ds in self.data[tipo]["datasets"]:
            for fila in ds["filas"]:
                if len(fila) < n_cols:
                    fila += [""] * (n_cols - len(fila))
                elif len(fila) > n_cols:
                    fila = fila[:n_cols]
                todas_filas.append(fila)
        df = pd.DataFrame(todas_filas, columns=headers)
        if "Año" in df.columns:
            df["Año"] = pd.to_numeric(df["Año"], errors='coerce').fillna(0).astype(int)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        # Actualizar metadatos
        self._actualizar_metadatos(tipo, self.data[tipo]["datasets"])

    # ---------- Visualización ----------
    def actualizar_info(self, *args):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        tipo = self.tipo_seleccionado.get()
        if tipo not in self.data or not self.data[tipo]["datasets"]:
            lbl = ttk.Label(self.scroll_frame, text="No hay datasets cargados para este tipo.",
                            background='white', font=('Segoe UI', 10))
            lbl.pack(pady=20)
            self.lbl_resumen.config(text="")
            return
        total_registros = 0
        total_datasets = len(self.data[tipo]["datasets"])
        for ds in self.data[tipo]["datasets"]:
            # Si los datos aún no se cargaron, usar el campo 'registros' del metadata
            if "registros" in ds and not ds["filas"]:
                total_registros += ds["registros"]
            else:
                total_registros += len(ds["filas"])
        self.lbl_resumen.config(text=f"📊 Total registros: {total_registros:,}  |  Datasets cargados: {total_datasets}")
        for idx, ds in enumerate(self.data[tipo]["datasets"]):
            self._crear_tarjeta_dataset(tipo, idx, ds)

    def _crear_tarjeta_dataset(self, tipo, idx, ds):
        card = tk.Frame(self.scroll_frame, bg='white', relief='solid', borderwidth=1,
                        highlightbackground=self.COLOR_PRIMARY, highlightthickness=1)
        card.pack(fill=tk.X, pady=5, padx=5, ipady=5)
        nombre_archivo = os.path.basename(ds["archivo"]) if ds["archivo"] else f"{tipo}.csv"
        # Determinar cantidad de registros (si hay datos reales o metadata)
        if "registros" in ds and not ds["filas"]:
            registros = ds["registros"]
        else:
            registros = len(ds["filas"])
        texto = f"{nombre_archivo}  |  Año: {ds['año']}  |  Registros: {registros}"
        lbl = tk.Label(card, text=texto, anchor='w', bg='white', fg=self.COLOR_PRIMARY,
                       font=('Segoe UI', 10, 'bold'))
        lbl.pack(side='left', padx=10, pady=8, fill=tk.X, expand=True)
        btn_del = ttk.Button(card, text="🗑️ Eliminar",
                             command=lambda t=tipo, i=idx: self.eliminar_dataset(t, i),
                             style='Danger.TButton')
        btn_del.pack(side='right', padx=5, pady=8)

    # ---------- Carga de archivos ----------
    def cargar_archivos(self):
        archivos = filedialog.askopenfilenames(
            title=f"Seleccionar archivos Excel de {self.tipo_seleccionado.get()}",
            filetypes=[("Archivos Excel", "*.xlsx *.xls"), ("Todos los archivos", "*.*")]
        )
        if not archivos:
            return
        for archivo in archivos:
            self.procesar_un_archivo(archivo)
            self.root.update()

    def procesar_un_archivo(self, archivo):
        tipo = self.tipo_seleccionado.get()
        nombre = os.path.basename(archivo)

        self.status_var.set(f"Analizando: {nombre}")
        self.progress_var.set(10)
        self.root.update()
        fila_inicio = self._detectar_fila_encabezado(archivo)

        try:
            df_a2 = pd.read_excel(archivo, sheet_name=0, header=None, nrows=2)
            titulo = str(df_a2.iloc[1, 0]) if df_a2.shape[0] > 1 else ""
        except:
            titulo = ""

        try:
            df_muestra = pd.read_excel(archivo, sheet_name=0, header=fila_inicio, nrows=100)
            if df_muestra.empty:
                messagebox.showwarning("Archivo vacío", f"{nombre}: no se encontraron datos.")
                return
            columnas_detectadas = [limpiar_nombre_columna(c) for c in df_muestra.columns]
            año = self._extraer_año_desde_df(df_muestra)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer {nombre}:\n{e}")
            return

        if not self._confirmar_encabezados(columnas_detectadas, archivo, año, titulo):
            self.status_var.set(f"Cancelado: {nombre}")
            self.progress_var.set(0)
            return

        self.progress_var.set(30)
        self.status_var.set(f"Procesando: {nombre}")
        self.root.update()

        try:
            df = pd.read_excel(archivo, sheet_name=0, header=fila_inicio)
            df.dropna(how="all", axis=1, inplace=True)
            df.dropna(how="all", axis=0, inplace=True)
            if df.empty:
                messagebox.showwarning("Sin datos", f"{nombre}: no hay datos después de la limpieza.")
                return

            # Cargar datos completos del tipo si aún no están en memoria
            self._cargar_datos_completos(tipo)

            nuevas_raw = list(df.columns)
            canonicas = self.obtener_canonicas(tipo)
            if canonicas is None:
                canonicas = [limpiar_nombre_columna(c) for c in nuevas_raw]

            mapeo = mapear_columnas_expandible(canonicas, nuevas_raw)

            # Construir DataFrame solo con canónicas
            df_consolidado = pd.DataFrame()
            for i, col_canonica in enumerate(canonicas):
                if mapeo.get(i) is not None:
                    idx_nuevo = mapeo[i]
                    df_consolidado[col_canonica] = df.iloc[:, idx_nuevo].values
                else:
                    df_consolidado[col_canonica] = pd.NA

            # Convertir a string (excepto Año)
            for col in df_consolidado.columns:
                if col != "Año":
                    df_consolidado[col] = df_consolidado[col].astype(str).replace("<NA>", "")

            año = self._extraer_año_desde_df(df_consolidado)
            if año is None:
                messagebox.showerror("Error", f"No se pudo determinar el año en {nombre}.")
                return
            df_consolidado["Año"] = año

            # Verificar duplicado de año
            if tipo in self.data:
                existente = next((ds for ds in self.data[tipo]["datasets"] if ds["año"] == año), None)
                if existente is not None:
                    if not messagebox.askyesno("Año duplicado",
                                               f"Ya existen datos para el año {año} en '{tipo}'.\n¿Desea reemplazarlos?"):
                        self.status_var.set(f"Omitido: {nombre} (año {año} ya existe)")
                        return

            nuevas_filas = df_consolidado.values.tolist()
            n_cols = len(canonicas)
            for i in range(len(nuevas_filas)):
                if len(nuevas_filas[i]) < n_cols:
                    nuevas_filas[i] += [""] * (n_cols - len(nuevas_filas[i]))
                elif len(nuevas_filas[i]) > n_cols:
                    nuevas_filas[i] = nuevas_filas[i][:n_cols]

            # Actualizar estructura
            if tipo not in self.data:
                self.data[tipo] = {"headers": canonicas, "datasets": []}
            # No se amplían las canónicas

            datasets = self.data[tipo]["datasets"]
            ds_existente = next((ds for ds in datasets if ds["año"] == año), None)
            if ds_existente:
                ds_existente["archivo"] = archivo
                ds_existente["fila_inicio"] = fila_inicio
                ds_existente["filas"] = nuevas_filas
                # Quitar el campo registros si existe para que use filas reales
                ds_existente.pop("registros", None)
            else:
                datasets.append({
                    "archivo": archivo,
                    "año": año,
                    "fila_inicio": fila_inicio,
                    "filas": nuevas_filas
                })

            self._actualizar_csv(tipo)
            self.progress_var.set(100)
            self.status_var.set(f"✔ {nombre} cargado (Año {año})")
            self.actualizar_info()

        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar {nombre}:\n{e}")

    # ---------- Eliminar dataset ----------
    def eliminar_dataset(self, tipo, idx):
        if not messagebox.askyesno("Eliminar dataset", "¿Está seguro de eliminar este dataset?\nSe borrarán sus registros del CSV maestro."):
            return
        # Asegurar que los datos reales están cargados
        self._cargar_datos_completos(tipo)
        del self.data[tipo]["datasets"][idx]
        if not self.data[tipo]["datasets"]:
            del self.data[tipo]
        self._actualizar_csv(tipo) if tipo in self.data else self._borrar_csv(tipo)
        self.status_var.set("🗑️ Dataset eliminado y CSV actualizado.")
        self.actualizar_info()

    def _borrar_csv(self, tipo):
        path = self._csv_path(tipo)
        if os.path.exists(path):
            os.remove(path)
        self._actualizar_metadatos(tipo, [])

    def limpiar_datos(self):
        tipo = self.tipo_seleccionado.get()
        if tipo in self.data:
            if messagebox.askyesno("Confirmar", f"¿Eliminar TODOS los datasets de '{tipo}' y borrar el CSV?"):
                del self.data[tipo]
                self._borrar_csv(tipo)
                self.status_var.set(f"🧹 Datos de '{tipo}' eliminados.")
                self.actualizar_info()
        else:
            messagebox.showinfo("Sin datos", "No hay datos para limpiar.")

    def ver_encabezados(self):
        tipo = self.tipo_seleccionado.get()
        canonicas = self.obtener_canonicas(tipo)
        if canonicas is None:
            messagebox.showinfo("Sin encabezados", f"No hay encabezados definidos para '{tipo}'.\nCargue el primer dataset.")
        else:
            win = tk.Toplevel(self.root)
            win.title(f"🔍 Encabezados de {tipo}")
            win.geometry("500x400")
            win.configure(bg='white')
            tk.Label(win, text=f"Columnas esperadas para {tipo}", font=('Segoe UI', 12, 'bold'),
                     bg='white', fg=self.COLOR_PRIMARY).pack(pady=10)
            texto = "\n".join(f"{i+1}. {col}" for i, col in enumerate(canonicas))
            text_widget = tk.Text(win, wrap='word', font=('Consolas', 10), bg='white', relief='flat', padx=20, pady=10)
            text_widget.insert('1.0', texto)
            text_widget.config(state='disabled')
            text_widget.pack(fill=tk.BOTH, expand=True)
            ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=10)

    def mostrar_acerca(self):
        messagebox.showinfo("Acerca de",
                            "Consolidador SNIES v3.7\n\n"
                            "Mapeo inteligente de columnas (Levenshtein + Jaccard).\n"
                            "Solo conserva las columnas maestras definidas.\n"
                            "Carga eficiente con metadatos.\n"
                            "Panel de resumen de datos.\n\n"
                            "Desarrollado por: Asistente DeepSeek AI")

    # Métodos auxiliares sin cambios (ya estaban en el código anterior)
    def obtener_canonicas(self, tipo):
        if tipo in self.FIXED_HEADERS:
            return self.FIXED_HEADERS[tipo]
        elif tipo in self.data:
            return self.data[tipo]["headers"]
        return None

    def _detectar_fila_encabezado(self, archivo):
        try:
            df_raw = pd.read_excel(archivo, sheet_name=0, header=None, nrows=20)
            best_row = 0
            best_score = -1
            for i, row in df_raw.iterrows():
                non_null = row.dropna()
                if len(non_null) == 0:
                    continue
                score = sum(1 for v in non_null if isinstance(v, str) and not v.replace('.','',1).isdigit())
                score += sum(len(str(v)) for v in non_null) / 10.0
                score -= sum(1 for v in non_null if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.','',1).isdigit())) * 2
                if score > best_score:
                    best_score = score
                    best_row = i
            return best_row
        except Exception:
            return 0

    def _extraer_año_desde_df(self, df):
        objetivos = ["año", "ano"]
        mejor_col = None
        mejor_sim = 0.0
        for col in df.columns:
            col_norm = normalizar_para_match(col)
            for obj in objetivos:
                sim = similitud_combinada(col_norm, obj)
                if sim > mejor_sim:
                    mejor_sim = sim
                    mejor_col = col
        if mejor_sim < 0.7:
            return None
        valores = df[mejor_col].dropna().unique()
        if len(valores) == 1:
            try:
                return int(float(valores[0]))
            except:
                return None
        elif len(valores) > 1:
            messagebox.showwarning("Año múltiple", f"Se encontraron varios años: {valores}. Se usará el primero.")
            return int(float(valores[0]))
        return None

    def _confirmar_encabezados(self, columnas, archivo, año, titulo):
        win = tk.Toplevel(self.root)
        win.title("Confirmar encabezados detectados")
        win.geometry("600x500")
        win.minsize(450, 400)
        win.configure(bg='white')
        win.transient(self.root)
        win.grab_set()

        info_frame = tk.Frame(win, bg='white')
        info_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(info_frame, text=f"📄 Archivo: {os.path.basename(archivo)}",
                 font=('Segoe UI', 10, 'bold'), bg='white', anchor='w').pack(anchor='w')
        if titulo:
            tk.Label(info_frame, text=f"📌 Título (A2): {titulo}",
                     font=('Segoe UI', 10), bg='white', anchor='w', wraplength=500).pack(anchor='w')
        if año is not None:
            tk.Label(info_frame, text=f"📅 Año detectado: {año}",
                     font=('Segoe UI', 10), bg='white', anchor='w').pack(anchor='w')
        else:
            tk.Label(info_frame, text="⚠️ No se pudo detectar el año automáticamente.",
                     font=('Segoe UI', 10), bg='white', fg='red', anchor='w').pack(anchor='w')

        tk.Label(win, text="Encabezados detectados:",
                 font=('Segoe UI', 11, 'bold'), bg='white', fg=self.COLOR_PRIMARY).pack(pady=(10,0))

        frame_txt = tk.Frame(win, bg='white')
        frame_txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = tk.Scrollbar(frame_txt)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(frame_txt, wrap='word', font=('Consolas', 9),
                              bg='white', relief='flat', yscrollcommand=scrollbar.set)
        texto = "\n".join(f"• {c}" for c in columnas)
        text_widget.insert('1.0', texto)
        text_widget.config(state='disabled', height=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        resultado = tk.BooleanVar(value=False)

        def aceptar():
            resultado.set(True)
            win.destroy()

        def cancelar():
            resultado.set(False)
            win.destroy()

        btn_frame = ttk.Frame(win, style='Card.TFrame', padding=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="✓ Sí, continuar", command=aceptar,
                   style='Success.TButton').pack(side='left', padx=20, expand=True)
        ttk.Button(btn_frame, text="✗ Cancelar", command=cancelar,
                   style='Danger.TButton').pack(side='right', padx=20, expand=True)

        win.wait_window()
        return resultado.get()

if __name__ == "__main__":
    root = tk.Tk()
    app = SNIESConsolidador(root)
    root.mainloop()