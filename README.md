# ProyectoFinalMineria

Estructura refactorizada para separar responsabilidades entre interfaz y lógica.

## Estructura del proyecto

app/
- config/
  - paths.py                      Configuración de rutas del proyecto
- core/
  - matching.py                   Lógica de similitud y mapeo de columnas
  - preprocessing_service.py      Lógica de carga, limpieza y guardado de CSV
- ui/
  - main_window.py                Interfaz principal de carga y consolidación
  - preprocessing_window.py       Interfaz de preprocesamiento visual

main.py                           Punto de entrada principal (wrapper)
preprocesamiento.py               Exportador de compatibilidad (wrapper)
data/                             Archivos CSV y metadatos

Flujo recomendado:

1. Cargar archivos Excel desde [main.py](main.py).
2. Consolidar y guardar CSV maestro en data/.
3. Preprocesar el CSV consolidado con una de estas opciones:
	 - Opción interactiva: botón Preprocesar CSV (abre la ventana de edición).
	 - Opción rápida: botón Preprocesar CSV actual (aplica limpieza base automática).

## Carga automática desde Google Drive

También puedes usar la opción `Cargar desde Google Drive` en el menú Archivo o en el panel de acciones.

Estructura esperada en Drive dentro de la carpeta `datos_snies`:

- Estudiantes_admitidos
- Estudiantes_inscritos
- Estudiantes_matriculados
- Estudiantes_matriculados_en_primer_curso
- Estudiantes_graduados
- Docentes
- Administrativos

Dentro de cada carpeta se leen archivos `.xlsx`, `.xls`, `.csv` y Google Sheets.
Las Google Sheets se exportan automáticamente a Excel para su procesamiento.

Requisitos:

1. Compartir la carpeta `datos_snies` con la cuenta de servicio de Google.
2. Tener el archivo de credenciales JSON de esa cuenta.
3. Al ejecutar la opción, ingresar el ID de la carpeta de Drive y seleccionar el JSON.

Qué hace cada módulo:

- [main.py](main.py)
	- Inicia la aplicación gráfica principal.

- [preprocesamiento.py](preprocesamiento.py)
	- Reexporta funciones y clases para mantener compatibilidad.

- [app/core/preprocessing_service.py](app/core/preprocessing_service.py)
	- Contiene el pipeline de limpieza de CSV sin dependencias de Tkinter.

- [app/ui/preprocessing_window.py](app/ui/preprocessing_window.py)
	- Contiene solo la interfaz de preprocesamiento.

- [app/ui/main_window.py](app/ui/main_window.py)
	- Contiene la interfaz principal y consume servicios de app/core.
