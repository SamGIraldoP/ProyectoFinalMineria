# EER SNIES (modelo relacional para generar código)

```mermaid
erDiagram
    DEPARTAMENTO {
        char(5) codigo PK
        varchar nombre
    }

    MUNICIPIO {
        char(5) codigo PK
        varchar nombre
        char(5) departamento_codigo FK
    }

    INSTITUCION {
        char(10) codigo PK
        varchar nombre
        varchar sector
        varchar caracter
        varchar tipo
        char(5) municipio_codigo FK
        char(10) ies_padre_codigo FK
    }

    AREA_CONOCIMIENTO {
        int id PK
        varchar nombre
    }

    NBC {
        int id PK
        varchar nombre
    }

    CINE_CAMPO_AMPLIO {
        int id PK
        varchar nombre
    }

    CINE_CAMPO_ESPECIFICO {
        int id PK
        varchar nombre
        int campo_amplio_id FK
    }

    CINE_DETALLADO {
        int id PK
        varchar nombre
        varchar codigo
        int campo_especifico_id FK
    }

    PROGRAMA {
        char(15) codigo_snies PK
        varchar nombre
        varchar nivel_academico
        varchar nivel_formacion
        varchar metodologia
        int area_id FK
        int nbc_id FK
        int cine_detallado_id FK
    }

    SEXO {
        tinyint id PK
        varchar nombre
    }

    NIVEL_FORMACION_DOCENTE {
        int id PK
        varchar nombre
    }

    TIEMPO_DEDICACION {
        int id PK
        varchar nombre
    }

    TIPO_CONTRATO {
        int id PK
        varchar nombre
    }

    HECHO_ADMINISTRATIVOS {
        bigint id PK
        char(10) institucion_codigo FK
        year anio
        tinyint semestre
        int auxiliar
        int tecnico
        int profesional
        int directivo
        int total
        timestamp created_at
    }

    HECHO_DOCENTES {
        bigint id PK
        char(10) institucion_codigo FK
        tinyint sexo_id FK
        int nivel_formacion_id FK
        int tiempo_dedicacion_id FK
        int tipo_contrato_id FK
        year anio
        tinyint semestre
        int num_docentes
        timestamp created_at
    }

    HECHO_ESTUDIANTES {
        bigint id PK
        char(10) institucion_codigo FK
        char(15) programa_codigo FK
        char(5) municipio_programa_codigo FK
        tinyint sexo_id FK
        year anio
        tinyint semestre
        int admitidos
        int inscritos
        int matriculados
        int graduados
        timestamp created_at
    }

    DEPARTAMENTO ||--o{ MUNICIPIO : contiene
    MUNICIPIO ||--o{ INSTITUCION : ubica
    INSTITUCION ||--o{ INSTITUCION : padre_de

    AREA_CONOCIMIENTO ||--o{ PROGRAMA : clasifica
    NBC ||--o{ PROGRAMA : agrupa
    CINE_CAMPO_AMPLIO ||--o{ CINE_CAMPO_ESPECIFICO : contiene
    CINE_CAMPO_ESPECIFICO ||--o{ CINE_DETALLADO : contiene
    CINE_DETALLADO ||--o{ PROGRAMA : clasifica

    INSTITUCION ||--o{ HECHO_ADMINISTRATIVOS : registra
    INSTITUCION ||--o{ HECHO_DOCENTES : registra
    INSTITUCION ||--o{ HECHO_ESTUDIANTES : registra

    SEXO ||--o{ HECHO_DOCENTES : clasifica
    SEXO ||--o{ HECHO_ESTUDIANTES : clasifica
    NIVEL_FORMACION_DOCENTE ||--o{ HECHO_DOCENTES : clasifica
    TIEMPO_DEDICACION ||--o{ HECHO_DOCENTES : clasifica
    TIPO_CONTRATO ||--o{ HECHO_DOCENTES : clasifica

    MUNICIPIO ||--o{ HECHO_ESTUDIANTES : oferta_en
    PROGRAMA ||--o{ HECHO_ESTUDIANTES : registra
```

## Lectura rápida del modelo

- **departamento 1:N municipio**
- **municipio 1:N institucion**
- **institucion 1:N institucion** por la relación de sede padre
- **programa** depende de **area_conocimiento**, **nbc** y **cine_detallado**
- **cine** queda en jerarquía de 3 niveles: **campo_amplio → campo_especifico → detallado**
- Los hechos quedan separados por dominio: **administrativos**, **docentes** y **estudiantes**

## Recomendación para tu programa

Si vas a generar las tablas desde código, este EER es ideal para implementar:
1. primero las tablas catálogo,
2. luego las dimensiones fuertes,
3. y al final las tablas de hechos.

Así evitas errores de claves foráneas durante la migración.

