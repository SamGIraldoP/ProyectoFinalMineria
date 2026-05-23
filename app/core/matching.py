import re
import unicodedata

UMBRAL = 0.6


def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def limpiar_nombre_columna(nombre: str) -> str:
    n = nombre.replace("\n", " ").strip()
    n = n.strip('"').strip("'")
    n = re.sub(r"\s+", " ", n)
    return n


def normalizar_para_match(nombre: str) -> str:
    nombre = nombre.lower()
    nombre = quitar_acentos(nombre)
    nombre = re.sub(r"[^a-z0-9\s]", "", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return nombre


def limpiar_texto_para_match(texto: str) -> str:
    texto = texto.lower()
    texto = quitar_acentos(texto)
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def levenshtein_ratio(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    m, n = len(s1), len(s2)
    d = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        d[i][0] = i
    for j in range(n + 1):
        d[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
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
