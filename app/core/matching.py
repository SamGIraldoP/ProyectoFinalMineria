import re
import unicodedata

from app.core.year_utils import (
    quitar_acentos,
    normalizar_para_match,
    levenshtein_ratio,
    similitud_combinada,
)

UMBRAL = 0.6

# Grupos de alias entre columnas que representan el mismo campo semántico.
_ALIAS_COLUMNAS = [
    {
        "principal o seccional",
        "tipo ies",
        "tipo de ies",
    },
    {
        "admitidos",
        "admisiones",
        "admision",
    },
    {
        "inscritos",
        "inscripciones",
        "inscripcion",
        "inscrito",
    },
    {
        "matriculados",
        "matriculados 2017",
    },
    {
        "no. de docentes",
        "no de docentes",
        "nro. de docentes",
        "nro de docentes",
        "n° de docentes",
        "nro. docentes",
        "docentes",
        "docente",
    },
    {
        "matriculados",
        "matriculados 2017",
    },
]


def limpiar_nombre_columna(nombre: str) -> str:
    n = nombre.replace("\n", " ").strip()
    n = n.strip('"').strip("'")
    n = re.sub(r"\s+", " ", n)
    return n


def limpiar_texto_para_match(texto: str) -> str:
    return normalizar_para_match(texto)


def _es_sexo_genero(cadena1: str, cadena2: str) -> bool:
    palabras = ['sexo', 'genero', 'género', 'sex', 'gender']
    c1 = normalizar_para_match(cadena1)
    c2 = normalizar_para_match(cadena2)
    if c1.startswith("id") or c2.startswith("id"):
        return False
    return any(p in c1 for p in palabras) and any(p in c2 for p in palabras)


def _es_alias_columna(cadena1: str, cadena2: str) -> bool:
    c1 = normalizar_para_match(cadena1)
    c2 = normalizar_para_match(cadena2)

    # Caso frecuente: columnas con sufijo de año, p. ej. "Admisiones 2018".
    if (("admitid" in c1) and ("admision" in c2)) or (("admitid" in c2) and ("admision" in c1)):
        return True
    # Análogo para inscritos/inscripciones
    if (("inscrit" in c1) and ("inscrip" in c2)) or (("inscrit" in c2) and ("inscrip" in c1)):
        return True
    if ("matriculad" in c1) and ("matriculad" in c2):
        return True

    for grupo in _ALIAS_COLUMNAS:
        if c1 in grupo and c2 in grupo:
            return True
    return False


def limpiar_flotante(s: str) -> str:
    if isinstance(s, str) and re.match(r'^-?\d+\.0$', s):
        return s[:-2]
    return s

def mapear_columnas_expandible(canonicas, nuevas_raw, umbral=UMBRAL):
    nuevas_limpias = [limpiar_nombre_columna(c) for c in nuevas_raw]
    canonicas_limpias = [limpiar_nombre_columna(c) for c in canonicas]

    parejas = []
    for i, cn in enumerate(canonicas_limpias):
        for j, nn in enumerate(nuevas_limpias):
            cn_norm = normalizar_para_match(cn)
            nn_norm = normalizar_para_match(nn)

            if cn_norm == nn_norm:
                sim = 1.0
            elif _es_sexo_genero(cn, nn):
                sim = 0.98
            elif _es_alias_columna(cn, nn):
                # Alias de alta prioridad, pero por debajo de coincidencia exacta.
                sim = 0.97
            else:
                sim = similitud_combinada(cn, nn)
            if re.search(r'\bid\b', nn):
                sim *= 0.8
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
