# ProyectoFinalMineria

Repositorio para ingestión, limpieza, emparejamiento y análisis de datos SNIES. La aplicación provee una interfaz gráfica para importar datos locales o desde Google Drive, ejecutar pipelines de limpieza y cargar resultados a MySQL.

## Documentación

- Documentación del sistema y arquitectura: [SISTEMA_COMPLETO.md](docs/SISTEMA_COMPLETO.md)
- Documentación paso a paso del pipeline: [PIPELINE_PASO_A_PASO.md](docs/PIPELINE_PASO_A_PASO.md)

## Resumen rápido

- Entradas: archivos `.csv`, `.xlsx`, `.xls` (locales o desde Google Drive).
- Carpeta de trabajo local para importaciones: `data/gdrive_import/`.
- Salida: CSV maestros en `data/` y (opcional) cargas a MySQL.

## Estructura principal

- `main.py` — punto de entrada de la aplicación GUI.
- `preprocesamiento.py` — utilidades de preprocesamiento y wrappers.
- `app/config/paths.py` — rutas y constantes del proyecto.
- `app/core/` — lógica de negocio: `google_drive_loader.py`, `preprocessing_service.py`, `matching.py`, `mysql_snies_setup.py`, `year_utils.py`.
- `app/ui/` — interfaces gráficas: `main_window.py`, `pipeline_window.py`, `preprocessing_window.py`, `google_drive_window.py`.
- `data/` — CSV de entrada, reportes y `gdrive_import/`.

## Quick start

1. Crear entorno virtual e instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Ejecutar la aplicación GUI:

```powershell
python main.py
```

3. Ejecutar solo el preprocesamiento (opcional):

```powershell
python preprocesamiento.py
```

## Ejecutar el pipeline automático por categorías

1. Abrir la ventana `Pipeline automatico por categorias` en la UI.
2. Proveer `ID carpeta Drive` y seleccionar `Credenciales JSON`.
3. Seleccionar categorías y presionar `Iniciar pipeline`.

El pipeline descargará archivos nuevos a `data/gdrive_import/`, integrará los archivos al CSV maestro, limpiará los datos y (si está configurado) insertará los datos en MySQL.

## Variables de entorno relevantes

- `GOOGLE_DRIVE_FOLDER_ID` (opcional) — ID de carpeta por defecto.
- `GOOGLE_DRIVE_CREDENTIALS_JSON_PATH` (opcional) — ruta por defecto al JSON de credenciales.
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` — conexión MySQL.

## Depuración y logs

- La UI muestra un panel de logs en `Pipeline automatico por categorias` con prefijos `[DRIVE]`, `[PIPELINE]`, `[MYSQL]`.
- Mensajes y errores críticos aparecen en la consola donde se ejecuta `main.py`.

## Contribuir

- Para cambios funcionales, crea una rama, realiza pruebas locales y abre una Pull Request.
- Mantén las reglas de `matching` y transformaciones versionadas (recomendado en archivos de configuración).

---

Si quieres, puedo añadir badges, ejemplos de configuración de `requirements.txt`, o actualizar automáticamente el `README` en el repositorio remoto (commit y push). 
