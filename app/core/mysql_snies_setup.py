from __future__ import annotations

from functools import reduce
from pathlib import Path
from typing import Callable
import os

import pandas as pd

from app.config.paths import DATA_DIR
from app.core.matching import normalizar_para_match
from app.core.preprocessing_service import mapear_sexo

DB_NAME = "snies"
CSV_DIR = Path(DATA_DIR)

ADMIN_FILE = "Administrativos.csv"
DOCENTE_FILE = "Docentes.csv"
STUDENT_FILES: dict[str, str] = {
    "Estudiantes_admitidos.csv": "admitidos",
    "Estudiantes_inscritos.csv": "inscritos",
    "Estudiantes_matriculados.csv": "matriculados",
    "Estudiantes_graduados.csv": "graduados",
}

ALIAS_MAP = {
    "institucion_codigo": ["Código de la Institución", "CÓDIGO DE LA INSTITUCIÓN"],
    "ies_padre_codigo": ["IES PADRE", "IES_PADRE"],
    "institucion_nombre": ["Institución de Educación Superior (IES)", "INSTITUCIÓN DE EDUCACIÓN SUPERIOR (IES)"],
    "principal_seccional": ["Principal o Seccional", "PRINCIPAL O SECCIONAL"],
    "sector_ies": ["Sector IES", "SECTOR IES"],
    "caracter_ies": ["Carácter IES", "CARACTER IES"],
    "departamento_ies_codigo": ["Código del departamento (IES)", "CÓDIGO DEL DEPARTAMENTO (IES)"],
    "departamento_ies_nombre": ["Departamento de domicilio de la IES", "DEPARTAMENTO DE DOMICILIO DE LA IES"],
    "municipio_ies_codigo": ["Código del Municipio (IES)", "Código del Municipio IES", "CÓDIGO DEL MUNICIPIO (IES)", "CÓDIGO DEL MUNICIPIO IES"],
    "municipio_ies_nombre": ["Municipio de domicilio de la IES", "MUNICIPIO DE DOMICILIO DE LA IES"],
    "anio": ["Año", "AÑO"],
    "semestre": ["Semestre", "SEMESTRE"],
    "auxiliar": ["Auxiliar", "AUXILIAR"],
    "tecnico": ["Técnico", "TECNICO"],
    "profesional": ["Profesional", "PROFESIONAL"],
    "directivo": ["Directivo", "DIRECTIVO"],
    "total": ["Total", "TOTAL"],
    "programa_codigo": ["Código SNIES del programa", "CÓDIGO SNIES DEL PROGRAMA"],
    "programa_nombre": ["Programa Académico", "PROGRAMA ACADÉMICO"],
    "nivel_academico": ["Nivel Académico", "NIVEL ACADÉMICO"],
    "nivel_formacion_programa": ["Nivel de Formación", "NIVEL DE FORMACIÓN"],
    "metodologia": ["Metodología", "METODOLOGÍA"],
    "area_conocimiento": ["Área de Conocimiento", "ÁREA DE CONOCIMIENTO"],
    "nbc": ["Núcleo Básico del Conocimiento (NBC)", "NÚCLEO BÁSICO DEL CONOCIMIENTO (NBC)"],
    "cine_campo_amplio": ["DESC CINE CAMPO AMPLIO"],
    "cine_campo_especifico": ["DESC CINE CAMPO ESPECIFICO"],
    "cine_detallado": ["DESC CINE CODIGO DETALLADO"],
    "departamento_programa_codigo": ["Código del Departamento (Programa)", "CÓDIGO DEL DEPARTAMENTO (PROGRAMA)"],
    "departamento_programa_nombre": ["Departamento de oferta del programa", "DEPARTAMENTO DE OFERTA DEL PROGRAMA"],
    "municipio_programa_codigo": ["Código del Municipio (Programa)", "CÓDIGO DEL MUNICIPIO (PROGRAMA)"],
    "municipio_programa_nombre": ["Municipio de oferta del programa", "MUNICIPIO DE OFERTA DEL PROGRAMA"],
    "sexo": ["Sexo", "SEXO", "Sexo del Docente"],
    "nivel_formacion_docente": ["Máximo nivel de formación del docente", "MÁXIMO NIVEL DE FORMACIÓN DEL DOCENTE"],
    "tiempo_dedicacion": ["Tiempo de dedicación del Docente", "TIEMPO DE DEDICACIÓN DEL DOCENTE"],
    "tipo_contrato": ["Tipo de contrato del Docente", "TIPO DE CONTRATO DEL DOCENTE"],
    "num_docentes": [
        "No. de Docentes",
        "NO. DE DOCENTES",
        "No de Docentes",
        "NO DE DOCENTES",
        "Nro. de docentes",
        "Nro de docentes",
        "NRO. DE DOCENTES",
        "NRO DE DOCENTES",
        "N° de Docentes",
        "N° de docentes",
        "Nro. docentes",
        "Nro. De DOCENTES",
        "DOCENTES",
        "Docentes",
        "DOCENTE",
    ],
    "admitidos": ["ADMITIDOS"],
    "inscritos": ["INSCRITOS"],
    "matriculados": ["Matriculados", "MATRICULADOS", "Matriculados 2017", "MATRICULADOS 2017"],
    "graduados": ["GRADUADOS"],
}


def _log_factory(progress_cb: Callable[[str], None] | None) -> Callable[[str], None]:
    def _log(message: str) -> None:
        print(f"[MySQL] {message}")
        if progress_cb is not None:
            progress_cb(message)

    return _log


def _normalize_key(value: object) -> str:
    if _is_missing(value):
        return ""
    return normalizar_para_match(str(value))


def _text(value: object) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _int(value: object, default: int = 0) -> int:
    if value == "" or _is_missing(value):
        return default
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _is_missing(value: object) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        return bool(value != value)
    except Exception:
        return False


def _first_non_empty(series: pd.Series) -> str | None:
    for value in series.tolist():
        text = _text(value)
        if text:
            return text
    return None


def _rename_by_aliases(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    normalized_columns = {_normalize_key(column): column for column in df.columns}
    for canonical, aliases in ALIAS_MAP.items():
        for alias in aliases:
            column = normalized_columns.get(_normalize_key(alias))
            if column is not None:
                rename_map[column] = canonical
                break
    return df.rename(columns=rename_map).copy()


def _read_csv(path_csv: Path) -> pd.DataFrame | None:
    if not path_csv.exists():
        return None
    df = pd.read_csv(path_csv, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    if df.empty:
        return None
    return _rename_by_aliases(df)


def _load_admin() -> pd.DataFrame | None:
    df = _read_csv(CSV_DIR / ADMIN_FILE)
    if df is None:
        return None
    columns = [
        "institucion_codigo",
        "ies_padre_codigo",
        "institucion_nombre",
        "principal_seccional",
        "sector_ies",
        "caracter_ies",
        "departamento_ies_codigo",
        "departamento_ies_nombre",
        "municipio_ies_codigo",
        "municipio_ies_nombre",
        "anio",
        "semestre",
        "auxiliar",
        "tecnico",
        "profesional",
        "directivo",
        "total",
    ]
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df[columns]


def _load_docentes() -> pd.DataFrame | None:
    df = _read_csv(CSV_DIR / DOCENTE_FILE)
    if df is None:
        return None
    columns = [
        "institucion_codigo",
        "ies_padre_codigo",
        "institucion_nombre",
        "principal_seccional",
        "sector_ies",
        "caracter_ies",
        "departamento_ies_codigo",
        "departamento_ies_nombre",
        "municipio_ies_codigo",
        "municipio_ies_nombre",
        "sexo",
        "nivel_formacion_docente",
        "tiempo_dedicacion",
        "tipo_contrato",
        "anio",
        "semestre",
        "num_docentes",
    ]
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df[columns]


def _load_students(path_csv: Path, measure_name: str) -> pd.DataFrame | None:
    df = _read_csv(path_csv)
    if df is None:
        return None
    if measure_name not in df.columns:
        df[measure_name] = 0
    df[measure_name] = pd.to_numeric(df[measure_name], errors="coerce").fillna(0).astype(int)
    columns = [
        "institucion_codigo",
        "ies_padre_codigo",
        "programa_codigo",
        "municipio_programa_codigo",
        "sexo",
        "anio",
        "semestre",
        measure_name,
        "institucion_nombre",
        "principal_seccional",
        "sector_ies",
        "caracter_ies",
        "departamento_ies_codigo",
        "departamento_ies_nombre",
        "municipio_ies_codigo",
        "municipio_ies_nombre",
        "programa_nombre",
        "nivel_academico",
        "nivel_formacion_programa",
        "metodologia",
        "area_conocimiento",
        "nbc",
        "cine_campo_amplio",
        "cine_campo_especifico",
        "cine_detallado",
        "departamento_programa_codigo",
        "departamento_programa_nombre",
        "municipio_programa_nombre",
    ]
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df[columns]


def _clean_value(value: object) -> str | None:
    text = _text(value)
    return text or None


def _ensure_database(cursor, log: Callable[[str], None]) -> None:
    cursor.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
        (DB_NAME,),
    )
    existed = cursor.fetchone() is not None
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    log(f"Base de datos '{DB_NAME}' {'ya existía' if existed else 'creada'}.")


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (DB_NAME, table_name),
    )
    return cursor.fetchone() is not None


def _table_row_count(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
    return int(cursor.fetchone()[0])


def _create_tables(cursor, log: Callable[[str], None]) -> None:
    ddl_statements = {
        "DEPARTAMENTO": """
            CREATE TABLE IF NOT EXISTS `DEPARTAMENTO` (
                `codigo` CHAR(5) NOT NULL,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`codigo`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "MUNICIPIO": """
            CREATE TABLE IF NOT EXISTS `MUNICIPIO` (
                `codigo` CHAR(5) NOT NULL,
                `nombre` VARCHAR(255) NOT NULL,
                `departamento_codigo` CHAR(5) NULL,
                PRIMARY KEY (`codigo`),
                KEY `idx_municipio_departamento` (`departamento_codigo`),
                CONSTRAINT `fk_municipio_departamento`
                    FOREIGN KEY (`departamento_codigo`) REFERENCES `DEPARTAMENTO` (`codigo`)
                    ON UPDATE CASCADE ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "INSTITUCION": """
            CREATE TABLE IF NOT EXISTS `INSTITUCION` (
                `codigo` CHAR(10) NOT NULL,
                `nombre` VARCHAR(255) NOT NULL,
                `sector` VARCHAR(255) NULL,
                `caracter` VARCHAR(255) NULL,
                `tipo` VARCHAR(255) NULL,
                `municipio_codigo` CHAR(5) NULL,
                `ies_padre_codigo` CHAR(10) NULL,
                PRIMARY KEY (`codigo`),
                KEY `idx_institucion_municipio` (`municipio_codigo`),
                KEY `idx_institucion_padre` (`ies_padre_codigo`),
                CONSTRAINT `fk_institucion_municipio`
                    FOREIGN KEY (`municipio_codigo`) REFERENCES `MUNICIPIO` (`codigo`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_institucion_padre`
                    FOREIGN KEY (`ies_padre_codigo`) REFERENCES `INSTITUCION` (`codigo`)
                    ON UPDATE CASCADE ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "AREA_CONOCIMIENTO": """
            CREATE TABLE IF NOT EXISTS `AREA_CONOCIMIENTO` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_area_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "NBC": """
            CREATE TABLE IF NOT EXISTS `NBC` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_nbc_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "CINE_CAMPO_AMPLIO": """
            CREATE TABLE IF NOT EXISTS `CINE_CAMPO_AMPLIO` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_cine_campo_amplio_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "CINE_CAMPO_ESPECIFICO": """
            CREATE TABLE IF NOT EXISTS `CINE_CAMPO_ESPECIFICO` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                `campo_amplio_id` INT NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_cine_campo_especifico` (`nombre`, `campo_amplio_id`),
                KEY `idx_cine_campo_especifico_amplio` (`campo_amplio_id`),
                CONSTRAINT `fk_cine_campo_especifico_amplio`
                    FOREIGN KEY (`campo_amplio_id`) REFERENCES `CINE_CAMPO_AMPLIO` (`id`)
                    ON UPDATE CASCADE ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "CINE_DETALLADO": """
            CREATE TABLE IF NOT EXISTS `CINE_DETALLADO` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                `codigo` VARCHAR(255) NOT NULL,
                `campo_especifico_id` INT NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_cine_detallado` (`codigo`, `campo_especifico_id`),
                KEY `idx_cine_detallado_especifico` (`campo_especifico_id`),
                CONSTRAINT `fk_cine_detallado_especifico`
                    FOREIGN KEY (`campo_especifico_id`) REFERENCES `CINE_CAMPO_ESPECIFICO` (`id`)
                    ON UPDATE CASCADE ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "PROGRAMA": """
            CREATE TABLE IF NOT EXISTS `PROGRAMA` (
                `codigo_snies` CHAR(15) NOT NULL,
                `nombre` VARCHAR(255) NOT NULL,
                `nivel_academico` VARCHAR(255) NULL,
                `nivel_formacion` VARCHAR(255) NULL,
                `metodologia` VARCHAR(255) NULL,
                `area_id` INT NULL,
                `nbc_id` INT NULL,
                `cine_detallado_id` INT NULL,
                PRIMARY KEY (`codigo_snies`),
                KEY `idx_programa_area` (`area_id`),
                KEY `idx_programa_nbc` (`nbc_id`),
                KEY `idx_programa_cine` (`cine_detallado_id`),
                CONSTRAINT `fk_programa_area`
                    FOREIGN KEY (`area_id`) REFERENCES `AREA_CONOCIMIENTO` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_programa_nbc`
                    FOREIGN KEY (`nbc_id`) REFERENCES `NBC` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_programa_cine`
                    FOREIGN KEY (`cine_detallado_id`) REFERENCES `CINE_DETALLADO` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "SEXO": """
            CREATE TABLE IF NOT EXISTS `SEXO` (
                `id` TINYINT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(50) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_sexo_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "NIVEL_FORMACION_DOCENTE": """
            CREATE TABLE IF NOT EXISTS `NIVEL_FORMACION_DOCENTE` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_nivel_formacion_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "TIEMPO_DEDICACION": """
            CREATE TABLE IF NOT EXISTS `TIEMPO_DEDICACION` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_tiempo_dedicacion_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "TIPO_CONTRATO": """
            CREATE TABLE IF NOT EXISTS `TIPO_CONTRATO` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `nombre` VARCHAR(255) NOT NULL,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_tipo_contrato_nombre` (`nombre`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "HECHO_ADMINISTRATIVOS": """
            CREATE TABLE IF NOT EXISTS `HECHO_ADMINISTRATIVOS` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                `institucion_codigo` CHAR(10) NOT NULL,
                `anio` INT NOT NULL,
                `semestre` TINYINT NOT NULL,
                `auxiliar` INT NOT NULL DEFAULT 0,
                `tecnico` INT NOT NULL DEFAULT 0,
                `profesional` INT NOT NULL DEFAULT 0,
                `directivo` INT NOT NULL DEFAULT 0,
                `total` INT NOT NULL DEFAULT 0,
                `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_hecho_admin_institucion` (`institucion_codigo`),
                CONSTRAINT `fk_hecho_admin_institucion`
                    FOREIGN KEY (`institucion_codigo`) REFERENCES `INSTITUCION` (`codigo`)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "HECHO_DOCENTES": """
            CREATE TABLE IF NOT EXISTS `HECHO_DOCENTES` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                `institucion_codigo` CHAR(10) NOT NULL,
                `sexo_id` TINYINT NULL,
                `nivel_formacion_id` INT NULL,
                `tiempo_dedicacion_id` INT NULL,
                `tipo_contrato_id` INT NULL,
                `anio` INT NOT NULL,
                `semestre` TINYINT NOT NULL,
                `num_docentes` INT NOT NULL DEFAULT 0,
                `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_hecho_docentes_institucion` (`institucion_codigo`),
                KEY `idx_hecho_docentes_sexo` (`sexo_id`),
                KEY `idx_hecho_docentes_nivel_formacion` (`nivel_formacion_id`),
                KEY `idx_hecho_docentes_tiempo` (`tiempo_dedicacion_id`),
                KEY `idx_hecho_docentes_tipo_contrato` (`tipo_contrato_id`),
                CONSTRAINT `fk_hecho_docentes_institucion`
                    FOREIGN KEY (`institucion_codigo`) REFERENCES `INSTITUCION` (`codigo`)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
                CONSTRAINT `fk_hecho_docentes_sexo`
                    FOREIGN KEY (`sexo_id`) REFERENCES `SEXO` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_hecho_docentes_nivel_formacion`
                    FOREIGN KEY (`nivel_formacion_id`) REFERENCES `NIVEL_FORMACION_DOCENTE` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_hecho_docentes_tiempo_dedicacion`
                    FOREIGN KEY (`tiempo_dedicacion_id`) REFERENCES `TIEMPO_DEDICACION` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_hecho_docentes_tipo_contrato`
                    FOREIGN KEY (`tipo_contrato_id`) REFERENCES `TIPO_CONTRATO` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        "HECHO_ESTUDIANTES": """
            CREATE TABLE IF NOT EXISTS `HECHO_ESTUDIANTES` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                `institucion_codigo` CHAR(10) NOT NULL,
                `programa_codigo` CHAR(15) NOT NULL,
                `municipio_programa_codigo` CHAR(5) NULL,
                `sexo_id` TINYINT NULL,
                `anio` INT NOT NULL,
                `semestre` TINYINT NOT NULL,
                `admitidos` INT NOT NULL DEFAULT 0,
                `inscritos` INT NOT NULL DEFAULT 0,
                `matriculados` INT NOT NULL DEFAULT 0,
                `graduados` INT NOT NULL DEFAULT 0,
                `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_hecho_estudiantes_institucion` (`institucion_codigo`),
                KEY `idx_hecho_estudiantes_programa` (`programa_codigo`),
                KEY `idx_hecho_estudiantes_municipio_programa` (`municipio_programa_codigo`),
                KEY `idx_hecho_estudiantes_sexo` (`sexo_id`),
                CONSTRAINT `fk_hecho_estudiantes_institucion`
                    FOREIGN KEY (`institucion_codigo`) REFERENCES `INSTITUCION` (`codigo`)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
                CONSTRAINT `fk_hecho_estudiantes_programa`
                    FOREIGN KEY (`programa_codigo`) REFERENCES `PROGRAMA` (`codigo_snies`)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
                CONSTRAINT `fk_hecho_estudiantes_municipio_programa`
                    FOREIGN KEY (`municipio_programa_codigo`) REFERENCES `MUNICIPIO` (`codigo`)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                CONSTRAINT `fk_hecho_estudiantes_sexo`
                    FOREIGN KEY (`sexo_id`) REFERENCES `SEXO` (`id`)
                    ON UPDATE CASCADE ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    }
    for table_name, ddl in ddl_statements.items():
        existed = _table_exists(cursor, table_name)
        cursor.execute(ddl)
        log(f"Tabla '{table_name}' {'ya existía' if existed else 'creada'}.")


def _insert_dataframe(cursor, table_name: str, columns: list[str], df: pd.DataFrame, log: Callable[[str], None], ignore: bool = True) -> None:
    if df is None or df.empty:
        log(f"Tabla '{table_name}': sin registros para insertar.")
        return
    query = "INSERT IGNORE" if ignore else "INSERT"
    sql = f"{query} INTO `{table_name}` ({', '.join(f'`{column}`' for column in columns)}) VALUES ({', '.join(['%s'] * len(columns))})"

    def _to_sql_value(value: object) -> object:
        if _is_missing(value):
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned != "" else None
        return value

    values = []
    for row in df[columns].itertuples(index=False, name=None):
        values.append(tuple(_to_sql_value(value) for value in row))
    cursor.executemany(sql, values)
    log(f"Tabla '{table_name}': {cursor.rowcount} registro(s) insertado(s).")


def _map_auto_ids(cursor, table_name: str) -> dict[object, int]:
    cursor.execute(f"SELECT * FROM `{table_name}`")
    columns = [description[0] for description in cursor.description]
    result: dict[object, int] = {}
    for row in cursor.fetchall():
        record = dict(zip(columns, row))
        if table_name in {
            "AREA_CONOCIMIENTO",
            "NBC",
            "CINE_CAMPO_AMPLIO",
            "SEXO",
            "NIVEL_FORMACION_DOCENTE",
            "TIEMPO_DEDICACION",
            "TIPO_CONTRATO",
        }:
            result[_normalize_key(record["nombre"])] = int(record["id"])
        elif table_name == "CINE_CAMPO_ESPECIFICO":
            result[(_normalize_key(record["nombre"]), int(record["campo_amplio_id"]))] = int(record["id"])
        elif table_name == "CINE_DETALLADO":
            result[(_normalize_key(record["codigo"]), int(record["campo_especifico_id"]))] = int(record["id"])
    return result


def _build_departamentos(*dfs: pd.DataFrame | None) -> pd.DataFrame:
    frames = []
    for df in dfs:
        if df is None or df.empty:
            continue
        for code_col, name_col in (("departamento_ies_codigo", "departamento_ies_nombre"), ("departamento_programa_codigo", "departamento_programa_nombre")):
            if code_col in df.columns and name_col in df.columns:
                frames.append(df[[code_col, name_col]].rename(columns={code_col: "codigo", name_col: "nombre"}))
    if not frames:
        return pd.DataFrame(columns=["codigo", "nombre"])
    data = pd.concat(frames, ignore_index=True)
    data["codigo"] = data["codigo"].map(_clean_value)
    data["nombre"] = data["nombre"].map(_clean_value)
    data = data.dropna(subset=["codigo"])
    data = data[data["codigo"] != ""]
    data = data.groupby("codigo", as_index=False).agg({"nombre": _first_non_empty})
    return data[data["nombre"].notna() & (data["nombre"] != "")]


def _build_municipios(*dfs: pd.DataFrame | None) -> pd.DataFrame:
    frames = []
    for df in dfs:
        if df is None or df.empty:
            continue
        for code_col, name_col, dept_col in (("municipio_ies_codigo", "municipio_ies_nombre", "departamento_ies_codigo"), ("municipio_programa_codigo", "municipio_programa_nombre", "departamento_programa_codigo")):
            if code_col in df.columns and name_col in df.columns and dept_col in df.columns:
                frames.append(df[[code_col, name_col, dept_col]].rename(columns={code_col: "codigo", name_col: "nombre", dept_col: "departamento_codigo"}))
    if not frames:
        return pd.DataFrame(columns=["codigo", "nombre", "departamento_codigo"])
    data = pd.concat(frames, ignore_index=True)
    for column in ["codigo", "nombre", "departamento_codigo"]:
        data[column] = data[column].map(_clean_value)
    data = data.dropna(subset=["codigo"])
    data = data[data["codigo"] != ""]
    data = data.groupby("codigo", as_index=False).agg({"nombre": _first_non_empty, "departamento_codigo": _first_non_empty})
    data["departamento_codigo"] = data["departamento_codigo"].replace({"": None})
    return data[data["nombre"].notna() & (data["nombre"] != "")]


def _build_instituciones(*dfs: pd.DataFrame | None) -> pd.DataFrame:
    frames = []
    for df in dfs:
        if df is None or df.empty or "institucion_codigo" not in df.columns:
            continue
        working = df.copy()
        for column in [
            "institucion_nombre",
            "sector_ies",
            "caracter_ies",
            "principal_seccional",
            "municipio_ies_codigo",
            "ies_padre_codigo",
        ]:
            if column not in working.columns:
                working[column] = pd.NA
        frames.append(
            working[
                [
                    "institucion_codigo",
                    "institucion_nombre",
                    "sector_ies",
                    "caracter_ies",
                    "principal_seccional",
                    "municipio_ies_codigo",
                    "ies_padre_codigo",
                ]
            ].rename(
                columns={
                    "institucion_codigo": "codigo",
                    "institucion_nombre": "nombre",
                    "sector_ies": "sector",
                    "caracter_ies": "caracter",
                    "principal_seccional": "tipo",
                    "municipio_ies_codigo": "municipio_codigo",
                    "ies_padre_codigo": "ies_padre_codigo",
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=["codigo", "nombre", "sector", "caracter", "tipo", "municipio_codigo", "ies_padre_codigo"])
    data = pd.concat(frames, ignore_index=True)
    for column in data.columns:
        data[column] = data[column].map(_clean_value)
    data = data.dropna(subset=["codigo"])
    data = data[data["codigo"] != ""]
    data["ies_padre_codigo"] = data.apply(
        lambda row: row["ies_padre_codigo"] if row["ies_padre_codigo"] and row["ies_padre_codigo"] != row["codigo"] else None,
        axis=1,
    )
    data = data.groupby("codigo", as_index=False).agg(
        {
            "nombre": _first_non_empty,
            "sector": _first_non_empty,
            "caracter": _first_non_empty,
            "tipo": _first_non_empty,
            "municipio_codigo": _first_non_empty,
            "ies_padre_codigo": _first_non_empty,
        }
    )
    return data[data["nombre"].notna() & (data["nombre"] != "")]


def _build_programas(*dfs: pd.DataFrame | None) -> pd.DataFrame:
    frames = []
    for df in dfs:
        if df is None or df.empty or "programa_codigo" not in df.columns:
            continue
        frames.append(
            df[
                [
                    "programa_codigo",
                    "programa_nombre",
                    "nivel_academico",
                    "nivel_formacion_programa",
                    "metodologia",
                    "area_conocimiento",
                    "nbc",
                    "cine_campo_amplio",
                    "cine_campo_especifico",
                    "cine_detallado",
                ]
            ].rename(
                columns={
                    "programa_codigo": "codigo_snies",
                    "programa_nombre": "nombre",
                    "nivel_formacion_programa": "nivel_formacion",
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=["codigo_snies", "nombre", "nivel_academico", "nivel_formacion", "metodologia", "area_conocimiento", "nbc", "cine_campo_amplio", "cine_campo_especifico", "cine_detallado"])
    data = pd.concat(frames, ignore_index=True)
    for column in data.columns:
        data[column] = data[column].map(_clean_value)
    data = data.dropna(subset=["codigo_snies"])
    data = data[data["codigo_snies"] != ""]
    data = data.groupby("codigo_snies", as_index=False).agg(
        {
            "nombre": _first_non_empty,
            "nivel_academico": _first_non_empty,
            "nivel_formacion": _first_non_empty,
            "metodologia": _first_non_empty,
            "area_conocimiento": _first_non_empty,
            "nbc": _first_non_empty,
            "cine_campo_amplio": _first_non_empty,
            "cine_campo_especifico": _first_non_empty,
            "cine_detallado": _first_non_empty,
        }
    )
    return data[data["nombre"].notna() & (data["nombre"] != "")]


def _build_text_dimension(column_name: str, *dfs: pd.DataFrame | None) -> pd.DataFrame:
    frames = []
    for df in dfs:
        if df is None or df.empty or column_name not in df.columns:
            continue
        frames.append(df[[column_name]].copy())
    if not frames:
        return pd.DataFrame(columns=[column_name])
    data = pd.concat(frames, ignore_index=True)
    data[column_name] = data[column_name].map(_clean_value)
    data = data.dropna(subset=[column_name])
    data = data[data[column_name] != ""]
    data = data.drop_duplicates(subset=[column_name]).reset_index(drop=True)
    return data


def _build_sexo_dimension(*dfs: pd.DataFrame | None) -> pd.DataFrame:
    frames = []
    for df in dfs:
        if df is None or df.empty or "sexo" not in df.columns:
            continue
        frames.append(df[["sexo"]].copy())
    if not frames:
        return pd.DataFrame(columns=["nombre"])
    data = pd.concat(frames, ignore_index=True)
    data["nombre"] = data["sexo"].map(mapear_sexo).map(_clean_value)
    data = data.dropna(subset=["nombre"])
    data = data[data["nombre"] != ""]
    data = data[["nombre"]].drop_duplicates().reset_index(drop=True)
    return data


def _build_cine_especifico(programas: pd.DataFrame, broad_map: dict[object, int]) -> pd.DataFrame:
    if programas.empty:
        return pd.DataFrame(columns=["nombre", "campo_amplio_id"])
    rows = []
    for _, row in programas.iterrows():
        broad_id = broad_map.get(_normalize_key(row["cine_campo_amplio"]))
        name = _clean_value(row["cine_campo_especifico"])
        if broad_id is None or not name:
            continue
        rows.append({"nombre": name, "campo_amplio_id": broad_id})
    if not rows:
        return pd.DataFrame(columns=["nombre", "campo_amplio_id"])
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def _build_cine_detallado(programas: pd.DataFrame, broad_map: dict[object, int], specific_map: dict[object, int]) -> pd.DataFrame:
    if programas.empty:
        return pd.DataFrame(columns=["nombre", "codigo", "campo_especifico_id"])
    rows = []
    for _, row in programas.iterrows():
        broad_id = broad_map.get(_normalize_key(row["cine_campo_amplio"]))
        if broad_id is None:
            continue
        specific_id = specific_map.get((_normalize_key(row["cine_campo_especifico"]), broad_id))
        code_or_name = _clean_value(row["cine_detallado"])
        if specific_id is None or not code_or_name:
            continue
        rows.append({"nombre": code_or_name, "codigo": code_or_name, "campo_especifico_id": specific_id})
    if not rows:
        return pd.DataFrame(columns=["nombre", "codigo", "campo_especifico_id"])
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def _build_fact_admin(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["institucion_codigo", "anio", "semestre", "auxiliar", "tecnico", "profesional", "directivo", "total"])
    data = df[["institucion_codigo", "anio", "semestre", "auxiliar", "tecnico", "profesional", "directivo", "total"]].copy()
    data["institucion_codigo"] = data["institucion_codigo"].map(_clean_value)
    for column in ["anio", "semestre", "auxiliar", "tecnico", "profesional", "directivo", "total"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(int)
    data = data.dropna(subset=["institucion_codigo"])
    data = data[data["institucion_codigo"] != ""]
    return data.groupby(["institucion_codigo", "anio", "semestre"], as_index=False)[["auxiliar", "tecnico", "profesional", "directivo", "total"]].sum().reset_index(drop=True)


def _build_fact_docentes(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["institucion_codigo", "sexo", "nivel_formacion_docente", "tiempo_dedicacion", "tipo_contrato", "anio", "semestre", "num_docentes"])
    data = df[["institucion_codigo", "sexo", "nivel_formacion_docente", "tiempo_dedicacion", "tipo_contrato", "anio", "semestre", "num_docentes"]].copy()
    for column in ["institucion_codigo", "sexo", "nivel_formacion_docente", "tiempo_dedicacion", "tipo_contrato"]:
        data[column] = data[column].map(_clean_value)
    for column in ["anio", "semestre", "num_docentes"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(int)
    data = data.dropna(subset=["institucion_codigo"])
    data = data[data["institucion_codigo"] != ""]
    return data.groupby(
        ["institucion_codigo", "sexo", "nivel_formacion_docente", "tiempo_dedicacion", "tipo_contrato", "anio", "semestre"],
        as_index=False,
    )[["num_docentes"]].sum().reset_index(drop=True)


def _build_fact_estudiantes(estudiantes: dict[str, pd.DataFrame | None]) -> pd.DataFrame:
    key_columns = ["institucion_codigo", "programa_codigo", "municipio_programa_codigo", "sexo", "anio", "semestre"]
    measure_frames = []
    for file_name, measure_name in STUDENT_FILES.items():
        df = estudiantes.get(file_name)
        if df is None or df.empty:
            continue
        data = df[key_columns + [measure_name]].copy()
        data["institucion_codigo"] = data["institucion_codigo"].map(_clean_value)
        data["programa_codigo"] = data["programa_codigo"].map(_clean_value)
        data["municipio_programa_codigo"] = data["municipio_programa_codigo"].map(_clean_value)
        data["sexo"] = data["sexo"].map(_clean_value)
        for column in ["anio", "semestre", measure_name]:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(int)
        data = data.dropna(subset=["institucion_codigo", "programa_codigo"])
        data = data[(data["institucion_codigo"] != "") & (data["programa_codigo"] != "")]
        data = data.groupby(key_columns, as_index=False)[measure_name].sum()
        measure_frames.append(data)
    if not measure_frames:
        return pd.DataFrame(columns=key_columns + ["admitidos", "inscritos", "matriculados", "graduados"])
    fact = reduce(lambda left, right: pd.merge(left, right, on=key_columns, how="outer"), measure_frames)
    for measure_name in ["admitidos", "inscritos", "matriculados", "graduados"]:
        if measure_name not in fact.columns:
            fact[measure_name] = 0
        fact[measure_name] = pd.to_numeric(fact[measure_name], errors="coerce").fillna(0).astype(int)
    fact["sexo"] = fact["sexo"].map(_clean_value)
    return fact


def _map_fk_text(df: pd.DataFrame, source_column: str, mapping: dict[object, int]) -> pd.Series:
    return df[source_column].map(lambda value: mapping.get(_normalize_key(value)))


def _map_fk_cine_especifico(df: pd.DataFrame, broad_map: dict[object, int], specific_map: dict[tuple[str, int], int]) -> pd.Series:
    def _resolve(row: pd.Series) -> int | None:
        broad_id = broad_map.get(_normalize_key(row["cine_campo_amplio"]))
        if broad_id is None:
            return None
        return specific_map.get((_normalize_key(row["cine_campo_especifico"]), broad_id))

    return df.apply(_resolve, axis=1)


def _map_fk_cine_detallado(df: pd.DataFrame, broad_map: dict[object, int], specific_map: dict[object, int], detail_map: dict[object, int]) -> pd.Series:
    def _resolve(row: pd.Series) -> int | None:
        broad_id = broad_map.get(_normalize_key(row["cine_campo_amplio"]))
        if broad_id is None:
            return None
        specific_id = specific_map.get((_normalize_key(row["cine_campo_especifico"]), broad_id))
        if specific_id is None:
            return None
        return detail_map.get((_normalize_key(row["cine_detallado"]), specific_id))

    return df.apply(_resolve, axis=1)


def _insert_if_empty(cursor, table_name: str, columns: list[str], df: pd.DataFrame, log: Callable[[str], None]) -> None:
    if _table_row_count(cursor, table_name) > 0:
        log(f"Tabla '{table_name}' ya contiene datos; se omite la inserción.")
        return
    _insert_dataframe(cursor, table_name, columns, df, log, ignore=False)


def _connect_mysql_server():
    import mysql.connector  # type: ignore[import-not-found]

    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    return mysql.connector.connect(host=host, port=port, user=user, password=password)


def _connect_mysql_database():
    import mysql.connector  # type: ignore[import-not-found]

    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    return mysql.connector.connect(host=host, port=port, user=user, password=password, database=DB_NAME)


def _load_all_csv_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict[str, pd.DataFrame | None]]:
    admin_df = _load_admin()
    docentes_df = _load_docentes()
    students: dict[str, pd.DataFrame | None] = {
        file_name: _load_students(CSV_DIR / file_name, measure_name)
        for file_name, measure_name in STUDENT_FILES.items()
    }
    return admin_df, docentes_df, students


def _insert_data_into_open_connection(
    cursor,
    connector_log: Callable[[str], None],
    admin_df: pd.DataFrame | None,
    docentes_df: pd.DataFrame | None,
    students: dict[str, pd.DataFrame | None],
) -> None:
    departamentos = _build_departamentos(admin_df, docentes_df, *students.values())
    municipios = _build_municipios(admin_df, docentes_df, *students.values())
    instituciones = _build_instituciones(admin_df, docentes_df, *students.values())
    programas = _build_programas(*students.values())
    areas = _build_text_dimension("area_conocimiento", *students.values())
    nbc = _build_text_dimension("nbc", *students.values())
    cine_amplio = _build_text_dimension("cine_campo_amplio", *students.values())
    sexo = _build_sexo_dimension(docentes_df, *students.values())
    nivel_formacion = _build_text_dimension("nivel_formacion_docente", docentes_df)
    tiempo_dedicacion = _build_text_dimension("tiempo_dedicacion", docentes_df)
    tipo_contrato = _build_text_dimension("tipo_contrato", docentes_df)

    _insert_dataframe(cursor, "DEPARTAMENTO", ["codigo", "nombre"], departamentos, connector_log)
    _insert_dataframe(cursor, "MUNICIPIO", ["codigo", "nombre", "departamento_codigo"], municipios, connector_log)
    _insert_dataframe(
        cursor,
        "INSTITUCION",
        ["codigo", "nombre", "sector", "caracter", "tipo", "municipio_codigo", "ies_padre_codigo"],
        instituciones,
        connector_log,
    )
    _insert_dataframe(cursor, "AREA_CONOCIMIENTO", ["nombre"], areas, connector_log)
    _insert_dataframe(cursor, "NBC", ["nombre"], nbc, connector_log)
    _insert_dataframe(cursor, "CINE_CAMPO_AMPLIO", ["nombre"], cine_amplio, connector_log)
    _insert_dataframe(cursor, "SEXO", ["nombre"], sexo, connector_log)
    _insert_dataframe(cursor, "NIVEL_FORMACION_DOCENTE", ["nombre"], nivel_formacion, connector_log)
    _insert_dataframe(cursor, "TIEMPO_DEDICACION", ["nombre"], tiempo_dedicacion, connector_log)
    _insert_dataframe(cursor, "TIPO_CONTRATO", ["nombre"], tipo_contrato, connector_log)

    broad_map = _map_auto_ids(cursor, "CINE_CAMPO_AMPLIO")
    cine_especifico = _build_cine_especifico(programas, broad_map)
    _insert_dataframe(cursor, "CINE_CAMPO_ESPECIFICO", ["nombre", "campo_amplio_id"], cine_especifico, connector_log)
    specific_map = _map_auto_ids(cursor, "CINE_CAMPO_ESPECIFICO")

    cine_detallado = _build_cine_detallado(programas, broad_map, specific_map)
    _insert_dataframe(cursor, "CINE_DETALLADO", ["nombre", "codigo", "campo_especifico_id"], cine_detallado, connector_log)
    detail_map = _map_auto_ids(cursor, "CINE_DETALLADO")

    area_map = _map_auto_ids(cursor, "AREA_CONOCIMIENTO")
    nbc_map = _map_auto_ids(cursor, "NBC")
    sexo_map = _map_auto_ids(cursor, "SEXO")
    nivel_formacion_map = _map_auto_ids(cursor, "NIVEL_FORMACION_DOCENTE")
    tiempo_dedicacion_map = _map_auto_ids(cursor, "TIEMPO_DEDICACION")
    tipo_contrato_map = _map_auto_ids(cursor, "TIPO_CONTRATO")

    programa_dim = programas.copy()
    programa_dim["area_id"] = _map_fk_text(programa_dim, "area_conocimiento", area_map)
    programa_dim["nbc_id"] = _map_fk_text(programa_dim, "nbc", nbc_map)
    programa_dim["cine_detallado_id"] = _map_fk_cine_detallado(programa_dim, broad_map, specific_map, detail_map)
    programa_dim = programa_dim[
        ["codigo_snies", "nombre", "nivel_academico", "nivel_formacion", "metodologia", "area_id", "nbc_id", "cine_detallado_id"]
    ]
    _insert_dataframe(
        cursor,
        "PROGRAMA",
        ["codigo_snies", "nombre", "nivel_academico", "nivel_formacion", "metodologia", "area_id", "nbc_id", "cine_detallado_id"],
        programa_dim,
        connector_log,
    )

    admin_fact = _build_fact_admin(admin_df)
    docentes_fact = _build_fact_docentes(docentes_df)
    estudiantes_fact = _build_fact_estudiantes(students)

    if not admin_fact.empty:
        _insert_if_empty(
            cursor,
            "HECHO_ADMINISTRATIVOS",
            ["institucion_codigo", "anio", "semestre", "auxiliar", "tecnico", "profesional", "directivo", "total"],
            admin_fact,
            connector_log,
        )
    else:
        connector_log("Tabla 'HECHO_ADMINISTRATIVOS': sin datos para cargar.")

    if not docentes_fact.empty:
        docentes_fact["sexo_id"] = _map_fk_text(docentes_fact, "sexo", sexo_map)
        docentes_fact["nivel_formacion_id"] = _map_fk_text(docentes_fact, "nivel_formacion_docente", nivel_formacion_map)
        docentes_fact["tiempo_dedicacion_id"] = _map_fk_text(docentes_fact, "tiempo_dedicacion", tiempo_dedicacion_map)
        docentes_fact["tipo_contrato_id"] = _map_fk_text(docentes_fact, "tipo_contrato", tipo_contrato_map)
        docentes_fact = docentes_fact[
            ["institucion_codigo", "sexo_id", "nivel_formacion_id", "tiempo_dedicacion_id", "tipo_contrato_id", "anio", "semestre", "num_docentes"]
        ]
        _insert_if_empty(
            cursor,
            "HECHO_DOCENTES",
            ["institucion_codigo", "sexo_id", "nivel_formacion_id", "tiempo_dedicacion_id", "tipo_contrato_id", "anio", "semestre", "num_docentes"],
            docentes_fact,
            connector_log,
        )
    else:
        connector_log("Tabla 'HECHO_DOCENTES': sin datos para cargar.")

    if not estudiantes_fact.empty:
        estudiantes_fact["sexo_id"] = _map_fk_text(estudiantes_fact, "sexo", sexo_map)
        estudiantes_fact = estudiantes_fact[
            ["institucion_codigo", "programa_codigo", "municipio_programa_codigo", "sexo_id", "anio", "semestre", "admitidos", "inscritos", "matriculados", "graduados"]
        ]
        _insert_if_empty(
            cursor,
            "HECHO_ESTUDIANTES",
            ["institucion_codigo", "programa_codigo", "municipio_programa_codigo", "sexo_id", "anio", "semestre", "admitidos", "inscritos", "matriculados", "graduados"],
            estudiantes_fact,
            connector_log,
        )
    else:
        connector_log("Tabla 'HECHO_ESTUDIANTES': sin datos para cargar.")


def _load_mysql(connector_log: Callable[[str], None], admin_df: pd.DataFrame | None, docentes_df: pd.DataFrame | None, students: dict[str, pd.DataFrame | None]) -> None:
    try:
        server_conn = _connect_mysql_server()
    except Exception as exc:
        raise RuntimeError(f"No se pudo conectar al servidor MySQL: {exc}") from exc

    try:
        server_conn.autocommit = True
        server_cursor = server_conn.cursor()
        _ensure_database(server_cursor, connector_log)
    finally:
        try:
            server_cursor.close()
        except Exception:
            pass
        server_conn.close()

    db_conn = _connect_mysql_database()
    try:
        db_conn.autocommit = False
        cursor = db_conn.cursor()
        _create_tables(cursor, connector_log)
        _insert_data_into_open_connection(cursor, connector_log, admin_df, docentes_df, students)
        db_conn.commit()
        connector_log("Carga a MySQL finalizada correctamente.")
    except Exception:
        db_conn.rollback()
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        db_conn.close()


def crear_base_y_tablas(progress_cb: Callable[[str], None] | None = None) -> bool:
    log = _log_factory(progress_cb)
    log("Creando/verificando base de datos y tablas SNIES en MySQL.")
    try:
        server_conn = _connect_mysql_server()
    except Exception as exc:
        log(f"No se pudo conectar al servidor MySQL: {exc}")
        return False

    try:
        server_conn.autocommit = True
        server_cursor = server_conn.cursor()
        _ensure_database(server_cursor, log)
    except Exception as exc:
        log(f"Error creando/verificando base de datos: {exc}")
        return False
    finally:
        try:
            server_cursor.close()
        except Exception:
            pass
        server_conn.close()

    try:
        db_conn = _connect_mysql_database()
    except Exception as exc:
        log(f"No se pudo conectar a la base '{DB_NAME}': {exc}")
        return False

    try:
        db_conn.autocommit = False
        cursor = db_conn.cursor()
        _create_tables(cursor, log)
        db_conn.commit()
        log("Creación/verificación de tablas finalizada correctamente.")
        return True
    except Exception as exc:
        db_conn.rollback()
        log(f"Error al crear tablas: {exc}")
        return False
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        db_conn.close()


def insertar_datos_csv(progress_cb: Callable[[str], None] | None = None) -> bool:
    log = _log_factory(progress_cb)
    log("Iniciando inserción manual de datos CSV a MySQL.")

    if not crear_base_y_tablas(progress_cb=progress_cb):
        log("Inserción cancelada: no fue posible preparar el esquema de base de datos.")
        return False

    admin_df, docentes_df, students = _load_all_csv_data()

    try:
        db_conn = _connect_mysql_database()
    except Exception as exc:
        log(f"No se pudo conectar a la base '{DB_NAME}': {exc}")
        return False

    try:
        db_conn.autocommit = False
        cursor = db_conn.cursor()
        _insert_data_into_open_connection(cursor, log, admin_df, docentes_df, students)
        db_conn.commit()
        log("Inserción de datos finalizada correctamente.")
        return True
    except Exception as exc:
        db_conn.rollback()
        log(f"Error durante la inserción de datos: {exc}")
        return False
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        db_conn.close()


def inicializar_base_datos_snies(progress_cb: Callable[[str], None] | None = None) -> bool:
    # Compatibilidad con llamadas previas: ahora usa el flujo manual completo.
    return insertar_datos_csv(progress_cb=progress_cb)


if __name__ == "__main__":
    inicializar_base_datos_snies()