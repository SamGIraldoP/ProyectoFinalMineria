import re
import unicodedata

import pandas as pd

from app.core.matching import limpiar_texto_para_match, levenshtein_ratio

NUMERIC_COLUMNS = [
    "Total",
    "Auxiliar",
    "Técnico",
    "Profesional",
    "Directivo",
    "ADMITIDOS",
    "GRADUADOS",
    "INSCRITOS",
    "Matriculados 2017",
    "No. de Docentes",
    "PRIMER CURSO",
]


def cargar_csv(path_csv: str) -> pd.DataFrame:
    return pd.read_csv(path_csv, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def guardar_csv(df: pd.DataFrame, path_csv: str) -> None:
    df.to_csv(path_csv, index=False, encoding="utf-8-sig")


def normalizar_texto(texto):
    if pd.isna(texto) or texto == "":
        return texto
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8")
    texto = texto.upper().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_instituciones(df: pd.DataFrame) -> pd.DataFrame:
    copia = df.copy()
    cols_ies = [col for col in copia.columns if "institucion" in col.lower()]
    for col in cols_ies:
        copia[col] = copia[col].apply(normalizar_texto)
    return copia


def convertir_tipos_df(df: pd.DataFrame) -> pd.DataFrame:
    copia = df.copy()
    if "Año" in copia.columns:
        copia["Año"] = pd.to_numeric(copia["Año"], errors="coerce").fillna(0).astype(int)
    for col in NUMERIC_COLUMNS:
        if col in copia.columns:
            copia[col] = pd.to_numeric(copia[col], errors="coerce").fillna(0).astype(int)
    return copia


def limpiar_df_base(df: pd.DataFrame) -> pd.DataFrame:
    copia = df.copy()
    copia = copia.dropna(how="all")
    copia = normalizar_instituciones(copia)
    copia = convertir_tipos_df(copia)
    return copia


def preprocesar_csv_maestro(path_csv: str, output_path: str = None) -> pd.DataFrame:
    df = cargar_csv(path_csv)
    df_limpio = limpiar_df_base(df)
    guardar_csv(df_limpio, output_path or path_csv)
    return df_limpio


def detectar_inconsistencias_df(sub_df: pd.DataFrame, umbral: float = 0.85):
    columnas_nombres = [
        col
        for col in sub_df.columns
        if any(
            palabra in col.lower()
            for palabra in [
                "institución",
                "institucion",
                "ies",
                "municipio",
                "departamento",
                "programa",
                "metodología",
                "metodologia",
                "área",
                "area",
                "núcleo",
                "nucleo",
            ]
        )
    ]
    reporte = []
    for col in columnas_nombres:
        n_unicos = sub_df[col].nunique()
        if n_unicos > 1000:
            continue
        conteo = sub_df[col].value_counts()
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
        for _, variantes in grupos.items():
            if len(variantes) > 1:
                canonico = max(variantes, key=lambda x: conteo[x])
                for var in variantes:
                    if var != canonico:
                        reporte.append(
                            {
                                "columna": col,
                                "valor_actual": var,
                                "valor_canonico": canonico,
                                "frecuencia_actual": conteo[var],
                                "frecuencia_canonico": conteo[canonico],
                            }
                        )
    return reporte
