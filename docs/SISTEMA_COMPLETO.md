**Resumen del Sistema**

Este repositorio implementa un sistema de ingestión, preprocesamiento, emparejamiento y análisis de datos SNIES, con una interfaz gráfica para orquestar cargas desde Google Drive, ejecutar pipelines de limpieza y revisar resultados. El sistema está organizado en módulos backend (app/core), configuración (app/config), interfaz (app/ui) y datos (data/).

**Arquitectura General**

- **Fuente de datos:** CSV locales en data/ y subcarpetas bajo data/gdrive_import/.
- **Carga remota:** carga desde Google Drive mediante el módulo de carga.
- **Preprocesamiento:** normalización, detección de años y limpieza de columnas.
- **Matching / Emparejamiento:** lógica para unir registros entre fuentes y producir salidas consolidadas.
- **Persistencia / BD:** configuración para MySQL (si se usa) en app/core/mysql_snies_setup.py.
- **Interfaz de usuario:** ventanas para importar, preprocesar y ejecutar pipelines.

**Componentes y Archivos Clave**

- **Entrada principal:** [main.py](main.py) — punto de arranque de la aplicación.
- **Configuración de rutas:** [app/config/paths.py](app/config/paths.py).
- **Carga desde Google Drive:** [app/core/google_drive_loader.py](app/core/google_drive_loader.py) y ventana [app/ui/google_drive_window.py](app/ui/google_drive_window.py).
- **Servicios de preprocesamiento:** [app/core/preprocessing_service.py](app/core/preprocessing_service.py) y el script preprocesamiento.py.
- **Emparejamiento y utilidades:** [app/core/matching.py](app/core/matching.py), [app/core/year_utils.py](app/core/year_utils.py).
- **Inicialización BD / setup:** [app/core/mysql_snies_setup.py](app/core/mysql_snies_setup.py).
- **Interfaz principal y ventanas:** [app/ui/main_window.py](app/ui/main_window.py), [app/ui/pipeline_window.py](app/ui/pipeline_window.py), [app/ui/preprocessing_window.py](app/ui/preprocessing_window.py).
- **Datasets de ejemplo:** archivos CSV en data/ (por ejemplo Estudiantes_matriculados.csv).

**Flujo de Datos Completo**

1. Ingestión
- Origenes: archivos locales en data/ y/o importación desde Google Drive.
- La importación desde Drive se realiza con las credenciales/configuración que la aplicación solicite y guarda copias en data/gdrive_import/.

2. Preprocesamiento
- Normalización de nombres de columnas y formatos (fechas, tipos numéricos).
- Detección de años y consistencia de periodos con year_utils.py.
- Limpieza: eliminación de filas duplicadas, normalización de textos, tratamiento de nulos.
- Todo esto se coordina desde preprocessing_service.py y/o la ventana de preprocesamiento.

3. Matching / Consolidación
- Aplicación de reglas de emparejamiento definidas en matching.py para identificar entidades equivalentes (p. ej., instituciones o programas).
- Fusión de registros y generación de tablas consolidadas para análisis.

4. Persistencia y salida
- Opcional: volcar resultados en una base MySQL usando mysql_snies_setup.py.
- Alternativa: exportar CSV/Reportes en data/ (por ejemplo year_detection_report.csv).

5. Análisis y Visualización
- Hay notebooks y herramientas adicionales (por ejemplo clustering_snies.ipynb) para análisis y agrupamiento de resultados.

**Flujo de la Interfaz de Usuario (UI)**

- **Ventana principal:** orchestración de acciones y acceso a las demás ventanas.
- **Importar desde Drive:** interfaz para seleccionar carpetas/archivos remotos, lanzar la descarga y ver el estado.
- **Preprocesamiento:** visualizar y ejecutar pasos de limpieza; opciones para ajustar reglas y ver previews.
- **Pipeline:** ejecutar secuencias completas (ingestión → preprocesamiento → matching → exportación) y ver logs/progreso.

**Cómo ejecutar el sistema (rápido)**

1. Crear un entorno virtual e instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Ejecutar la aplicación (GUI o CLI según implementación en main.py):

```powershell
python main.py
```

3. Ejecutar preprocesamiento por separado (si se desea):

```powershell
python preprocesamiento.py
```

**Mapa de archivos (resumen rápido)**

- **Raíz del proyecto:** main.py, preprocesamiento.py, requirements.txt, README.md.
- **app/config:** app/config/paths.py — rutas y constantes.
- **app/core:** módulos de carga, matching, preprocesamiento y utilidades.
- **app/ui:** ventanas para Google Drive, pipeline y preprocesamiento.
- **data:** CSV de entrada, reportes y subcarpetas gdrive_import/.

**Buenas prácticas y notas**

- Mantener una copia local de los datos importados desde Drive en data/gdrive_import/ para reproducibilidad.
- Versionar reglas de matching y transformaciones (idealmente en un archivo de configuración o en control de versiones).
- Validar esquemas de CSV antes de ejecutar pipelines largos; usar previews en la UI.

**Siguientes pasos recomendados**

- Añadir un README de ejecución (si no existe) con credenciales y permisos necesarios para Google Drive.
- Convertir reglas de matching en configuraciones externas para facilitar ajustes.

Fin del documento.
