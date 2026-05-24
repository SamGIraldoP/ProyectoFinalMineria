import re
import unicodedata
from functools import lru_cache
from typing import Optional, Sequence, Tuple
from collections import Counter

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox


# =========================================================
# Utilidades de normalización y similitud
# =========================================================

YEAR_COLUMN_TARGETS = ("año", "ano")
DEFAULT_YEAR_COLUMN_THRESHOLD = 0.7


@lru_cache(maxsize=1024)
def quitar_acentos(texto: str) -> str:
    texto = "" if texto is None else str(texto)
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@lru_cache(maxsize=2048)
def normalizar_para_match(texto: str) -> str:
    texto = "" if texto is None else str(texto)
    texto = texto.lower()
    texto = quitar_acentos(texto)
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def levenshtein_ratio(s1: str, s2: str) -> float:
    s1 = normalizar_para_match(s1)
    s2 = normalizar_para_match(s2)

    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    m, n = len(s1), len(s2)
    d = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        d[i][0] = i
    for j in range(n + 1):
        d[0][j] = j

    for i in range(1, m + 1):
        c1 = s1[i - 1]
        for j in range(1, n + 1):
            cost = 0 if c1 == s2[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )

    return 1 - d[m][n] / max(m, n)


def similitud_combinada(cadena1: str, cadena2: str) -> float:
    s1 = normalizar_para_match(cadena1)
    s2 = normalizar_para_match(cadena2)

    lev = levenshtein_ratio(s1, s2)
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())

    if not tokens1 and not tokens2:
        jaccard = 1.0
    elif not tokens1 or not tokens2:
        jaccard = 0.0
    else:
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)

    return max(lev, jaccard)


# =========================================================
# Conversión y validación de año
# =========================================================


def convertir_a_entero_si_es_año(valor) -> Optional[int]:
    if valor is None:
        return None

    texto = str(valor).strip()
    if not texto or texto.lower() in {"nan", "none", "<na>"}:
        return None

    if re.fullmatch(r"\d{4}", texto):
        año = int(texto)
        return año if 1900 <= año <= 2100 else None

    if re.fullmatch(r"\d{4}\.0", texto):
        año = int(float(texto))
        return año if 1900 <= año <= 2100 else None

    try:
        numero = float(texto)
        if numero.is_integer():
            año = int(numero)
            return año if 1900 <= año <= 2100 else None
    except ValueError:
        return None

    return None


def obtener_años_validos_desde_serie(serie) -> list:
    años = []
    vistos = set()
    for valor in serie.dropna().unique():
        año = convertir_a_entero_si_es_año(valor)
        if año is not None and año not in vistos:
            vistos.add(año)
            años.append(año)
    años.sort()
    return años


# =========================================================
# Extracción de años desde texto libre y dataframe
# =========================================================


def extraer_años_de_texto(texto: str) -> list:
    """Extrae todos los años válidos (entero entre 1900 y 2100) de una cadena de texto.

    Devuelve una lista de enteros (posiblemente vacía), preservando el orden de aparición.
    """
    if texto is None:
        return []
    s = str(texto)
    # Normalizar acentos para mejorar coincidencias en algunos encabezados
    s = quitar_acentos(s)
    # Buscar patrones de año como '2018', 'AÑO 2024', ' - 2019', etc.
    matches = re.findall(r"\b(19\d{2}|20\d{2}|2100)\b", s)
    años = []
    for m in matches:
        try:
            a = int(m)
            if 1900 <= a <= 2100:
                años.append(a)
        except ValueError:
            continue
    return años


def extraer_años_desde_dataframe_scan(df, max_head_rows: int = 10) -> list:
    """Escanea columnas, cabeceras y primeras filas para encontrar años mencionados en texto libre.

    Retorna una lista de años encontrados ordenada por frecuencia (más común primero).
    """
    contador = Counter()

    # Escanear nombres de columnas
    for col in df.columns:
        for a in extraer_años_de_texto(col):
            contador[a] += 2  # columnas pesan un poco más

    # Escanear valores de las primeras filas (o todas si son pocas)
    n_rows = min(len(df), max_head_rows)
    if n_rows > 0:
        head = df.head(n_rows)
        for _, row in head.iterrows():
            for v in row:
                for a in extraer_años_de_texto(v):
                    contador[a] += 1

    # Escanear índice y nombres de índice
    if hasattr(df, 'index') and df.index is not None:
        for idx in df.index[:max_head_rows]:
            for a in extraer_años_de_texto(idx):
                contador[a] += 1

    # Si no encontramos nada en el head, escanear todo el dataframe como último recurso
    if not contador:
        for col in df.columns:
            try:
                for v in df[col].dropna().astype(str).unique():
                    for a in extraer_años_de_texto(v):
                        contador[a] += 1
            except Exception:
                continue

    # Ordenar por frecuencia y devolver la lista de años
    if not contador:
        return []
    return [a for a, _ in contador.most_common()]


def extraer_año_desde_archivo(path_archivo: str, max_rows: int = 40, sheet_name=None) -> Optional[int]:
    """Intenta detectar el año directamente desde el archivo (Excel/CSV) sin depender del mapeo de columnas.

    Estrategia:
    1) Escanear primeras filas crudas del archivo.
    2) Escanear contenido de texto inicial del archivo.
    3) Usar nombre del archivo como último recurso.
    """
    if not path_archivo:
        return None

    path = str(path_archivo)
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""

    # 1) Escaneo de primeras filas crudas
    try:
        import pandas as pd

        if ext in {"xlsx", "xls", "xlsm", "xlsb"}:
            # Si se indica hoja, priorizarla; de lo contrario recorrer varias hojas.
            if sheet_name is not None:
                hojas = [sheet_name]
            else:
                try:
                    xls = pd.ExcelFile(path_archivo)
                    hojas = xls.sheet_names[:8]
                except Exception:
                    hojas = [0]

            contador = Counter()
            for hoja in hojas:
                try:
                    df_raw = pd.read_excel(path_archivo, sheet_name=hoja, header=None, nrows=max_rows)
                except Exception:
                    continue
                if df_raw is None or df_raw.empty:
                    continue
                años = extraer_años_desde_dataframe_scan(df_raw, max_head_rows=max_rows)
                for pos, a in enumerate(años):
                    # Mayor peso al primer año detectado por hoja.
                    contador[a] += max(1, 4 - pos)

            if contador:
                return contador.most_common(1)[0][0]
        elif ext in {"csv", "txt"}:
            try:
                df_raw = pd.read_csv(path_archivo, header=None, nrows=max_rows, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            except Exception:
                df_raw = pd.read_csv(path_archivo, header=None, nrows=max_rows, dtype=str, keep_default_na=False, encoding="latin1")
            if df_raw is not None and not df_raw.empty:
                años = extraer_años_desde_dataframe_scan(df_raw, max_head_rows=max_rows)
                if años:
                    return años[0]
    except Exception:
        pass

    # 2) Escaneo de contenido textual inicial
    try:
        with open(path_archivo, "rb") as f:
            raw = f.read(12000)
        texto = raw.decode("utf-8", errors="ignore")
        años = extraer_años_de_texto(texto)
        if años:
            return años[0]
    except Exception:
        pass

    # 3) Último recurso: nombre del archivo
    try:
        import os

        nombre = os.path.basename(path_archivo)
        años = extraer_años_de_texto(nombre)
        if años:
            return años[0]
    except Exception:
        pass

    return None


# =========================================================
# Detección de columna de año
# =========================================================


def buscar_mejor_columna_año(
    columnas: Sequence[str],
    objetivos: Sequence[str] = YEAR_COLUMN_TARGETS,
) -> Tuple[Optional[str], float]:
    mejor_col = None
    mejor_sim = 0.0
    for col in columnas:
        for objetivo in objetivos:
            sim = similitud_combinada(col, objetivo)
            if sim > mejor_sim:
                mejor_sim = sim
                mejor_col = col
    return mejor_col, mejor_sim


def get_año_col_name(df) -> Optional[str]:
    for col in df.columns:
        if normalizar_para_match(col) in YEAR_COLUMN_TARGETS:
            return col
    return None


# =========================================================
# Interacción opcional con UI (Tkinter)
# =========================================================


def pedir_año_manual() -> Optional[int]:
    año_str = simpledialog.askstring(
        "Año no detectado",
        "No se pudo detectar el año automáticamente.\nIngrese el año manualmente:"
    )
    if año_str is None:
        return None
    año = convertir_a_entero_si_es_año(año_str)
    if año is None:
        messagebox.showerror("Error", "Año inválido.")
        return None
    return año


def seleccionar_año_interactivo(root: tk.Misc, años_validos: Sequence[int]) -> Optional[int]:
    if not años_validos:
        return None
    if len(años_validos) == 1:
        return int(años_validos[0])

    ventana = tk.Toplevel(root)
    ventana.title("Seleccionar año")
    ventana.geometry("300x150")
    ventana.configure(bg="white")
    ventana.transient(root)
    ventana.grab_set()

    tk.Label(
        ventana,
        text="Se encontraron varios años.\nSeleccione el año correcto:",
        bg="white"
    ).pack(pady=10)

    año_var = tk.StringVar(value=str(años_validos[0]))
    cb = ttk.Combobox(
        ventana,
        textvariable=año_var,
        values=[str(a) for a in años_validos],
        state="readonly"
    )
    cb.pack(pady=5)

    resultado = {"año": None}

    def aceptar():
        resultado["año"] = int(año_var.get())
        ventana.destroy()

    def cancelar():
        ventana.destroy()

    btn_frame = ttk.Frame(ventana)
    btn_frame.pack(pady=10)
    ttk.Button(btn_frame, text="Aceptar", command=aceptar).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=cancelar).pack(side="left", padx=5)

    ventana.wait_window()
    return resultado["año"]


# =========================================================
# Función principal reutilizable
# =========================================================


def extraer_año_desde_dataframe(
    df,
    *,
    root: Optional[tk.Misc] = None,
    threshold: float = DEFAULT_YEAR_COLUMN_THRESHOLD,
    pedir_manual_si_falla: bool = True,
) -> Optional[int]:
    mejor_col, mejor_sim = buscar_mejor_columna_año(df.columns)
    if mejor_col is None or mejor_sim < threshold:
        # Intentar detectar año buscando en texto libre (encabezados, primeras celdas, etc.)
        años_en_texto = extraer_años_desde_dataframe_scan(df)
        if años_en_texto:
            return años_en_texto[0]
        if pedir_manual_si_falla:
            return pedir_año_manual()
        return None

    años_validos = obtener_años_validos_desde_serie(df[mejor_col])
    if not años_validos:
        # Si la columna candidata no contiene años, intentar escanear texto libre
        años_en_texto = extraer_años_desde_dataframe_scan(df)
        if años_en_texto:
            return años_en_texto[0]
        if pedir_manual_si_falla:
            return pedir_año_manual()
        return None
    if len(años_validos) == 1:
        return años_validos[0]
    if root is not None:
        return seleccionar_año_interactivo(root, años_validos)
    return años_validos[0]


# =========================================================
# Helpers de integración con la app
# =========================================================


def extraer_año_interactivo_desde_app(app, df) -> Optional[int]:
    return extraer_año_desde_dataframe(
        df,
        root=app.root,
        threshold=DEFAULT_YEAR_COLUMN_THRESHOLD,
        pedir_manual_si_falla=True,
    )


def asignar_año_a_dataframe(df, año: int) -> bool:
    col_año = get_año_col_name(df)
    if not col_año:
        return False
    df[col_año] = año
    return True
