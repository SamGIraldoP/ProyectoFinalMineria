import re
import unicodedata

import pandas as pd

from app.core.matching import limpiar_texto_para_match, levenshtein_ratio, quitar_acentos

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

VALORES_NULOS_TEXTO = frozenset(
    {
        "sin informacion",
        "sin info",
        "sinformacion",
        "sin informacion disponible",
        "no disponible",
        "nd",
        "n/d",
        "na",
        "n/a",
        "no aplica",
        "no data",
        "no registra",
        "no registrado",
        "sin dato",
        "sin datos",
        "sin registro",
        "desconocido",
        "desconocida",
        "ninguno",
        "ninguna",
        "null",
        "none",
        "nan",
        "no hay informacion",
        "no hay datos",
    }
)

_PATRONES_MASCULINO = [
    "masculino",
    "hombre",
    "male",
    "varon",
    "masc",
    "m",
    "h",
    "masculino (hombre)",
    "hombre (masculino)",
]

_PATRONES_FEMENINO = [
    "femenino",
    "mujer",
    "female",
    "fem",
    "f",
    "w",
    "muj",
    "femenino (mujer)",
    "mujer (femenino)",
]

_PATRONES_M_LIMPIOS = [limpiar_texto_para_match(p) for p in _PATRONES_MASCULINO]
_PATRONES_F_LIMPIOS = [limpiar_texto_para_match(p) for p in _PATRONES_FEMENINO]
_UMBRAL_SEXO = 0.7


def cargar_csv(path_csv: str) -> pd.DataFrame:
    return pd.read_csv(path_csv, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def guardar_csv(df: pd.DataFrame, path_csv: str) -> None:
    df.to_csv(path_csv, index=False, encoding="utf-8-sig")


def normalizar_texto(texto):
    if pd.isna(texto) or texto == "":
        return texto
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("ascii")
    texto = texto.upper().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def es_valor_nulo_texto(valor: str) -> bool:
    if not isinstance(valor, str):
        return False
    if not valor.strip():
        return True
    return limpiar_texto_para_match(valor) in VALORES_NULOS_TEXTO


def nulificar_celdas_vacias_df(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    copia = df.copy()
    mask_vacia = copia.applymap(lambda v: isinstance(v, str) and not v.strip())
    mask_sin_info = (~mask_vacia) & copia.applymap(
        lambda v: isinstance(v, str) and es_valor_nulo_texto(v)
    )
    n_vacias = int(mask_vacia.sum().sum())
    n_sin_info = int(mask_sin_info.sum().sum())
    copia[mask_vacia | mask_sin_info] = pd.NA
    return copia, n_vacias, n_sin_info


def normalizar_instituciones(df: pd.DataFrame) -> pd.DataFrame:
    copia = df.copy()
    cols_ies = [col for col in copia.columns if "institucion" in col.lower()]
    for col in cols_ies:
        copia[col] = copia[col].apply(normalizar_texto)
    return copia


def mapear_sexo(valor: str) -> str:
    if not isinstance(valor, str):
        return valor
    limpio = limpiar_texto_para_match(valor)
    if not limpio:
        return valor
    sim_m = max(levenshtein_ratio(limpio, p) for p in _PATRONES_M_LIMPIOS)
    sim_f = max(levenshtein_ratio(limpio, p) for p in _PATRONES_F_LIMPIOS)
    if sim_m >= _UMBRAL_SEXO and sim_m > sim_f:
        return "Masculino"
    if sim_f >= _UMBRAL_SEXO and sim_f > sim_m:
        return "Femenino"
    return valor


def normalizar_sexo_df(df: pd.DataFrame) -> pd.DataFrame:
    copia = df.copy()
    cols_sexo = [
        col
        for col in copia.columns
        if any(p in quitar_acentos(col.lower()) for p in ("sexo", "genero"))
    ]
    for col in cols_sexo:
        mask_nonempty = copia[col].notna() & (copia[col] != "")
        copia.loc[mask_nonempty, col] = copia.loc[mask_nonempty, col].map(mapear_sexo)
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
    copia, _, _ = nulificar_celdas_vacias_df(copia)
    copia = copia.dropna(how="all")
    copia = normalizar_instituciones(copia)
    copia = normalizar_sexo_df(copia)
    copia = convertir_tipos_df(copia)
    return copia


def preprocesar_csv_maestro(path_csv: str, output_path: str = None) -> pd.DataFrame:
    df = cargar_csv(path_csv)
    df_limpio = limpiar_df_base(df)
    guardar_csv(df_limpio, output_path or path_csv)
    return df_limpio


def detectar_inconsistencias_df(sub_df: pd.DataFrame, umbral: float = 0.85):
    palabras_objetivo = {
        "institucion",
        "ies",
        "municipio",
        "departamento",
        "programa",
        "metodologia",
        "area",
        "nucleo",
    }
    columnas_nombres = [
        col
        for col in sub_df.columns
        if any(palabra in quitar_acentos(col.lower()) for palabra in palabras_objetivo)
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
        cache_limpio = {nombre: limpiar_texto_para_match(nombre) for nombre in top_nombres}
        grupos = {}
        for nombre in top_nombres:
            nombre_limpio = cache_limpio[nombre]
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
