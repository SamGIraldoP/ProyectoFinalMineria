# Pipeline: Proceso paso a paso

Este documento describe de forma detallada y secuencial el comportamiento del pipeline automático por categorías que se ejecuta desde la interfaz (app/ui/pipeline_window.py). El objetivo es explicar qué hace el pipeline en cada etapa, qué archivos toca y cómo manejar fallos.

**Precondiciones**

- Tener instalado y configurado el proyecto (entorno, dependencias en requirements.txt).
- Proveer: ID de carpeta de Google Drive (folder_id) y ruta al archivo de credenciales de servicio JSON.
- La aplicación mantiene una carpeta de trabajo local en DATA_DIR/gdrive_import/ donde guarda los archivos descargados.
- La variable FOLDER_TO_TIPO (en app/core/google_drive_loader.py) mapea subcarpetas de Drive a categorías internas.

---

## Resumen de etapas (alto nivel)

1. Detectar y descargar archivos nuevos desde Google Drive.
2. Integrar archivos nuevos en el CSV maestro de la categoría (si los hay).
3. Ejecutar limpieza/preprocesamiento del CSV maestro (preprocesar_csv_maestro).
4. Insertar los datos limpios en MySQL (opcional según configuración) usando insertar_datos_csv.
5. Informar resultados y mostrar resumen al usuario.

---

## Flujo paso a paso (detallado)

1) Validaciones iniciales

- El usuario selecciona las categorías a procesar, ingresa folder_id y selecciona el archivo de credenciales JSON.
- El pipeline verifica que las entradas no estén vacías y que el archivo JSON exista. Si falta algo, muestra un messagebox y detiene la ejecución.

2) Confirmación

- Se solicita confirmación al usuario indicando las categorías que se procesarán y que el proceso puede tardar varios minutos.

3) Paso 1/4 — Búsqueda y descarga desde Google Drive

- Se lista el contenido actual en DATA_DIR/gdrive_import/ por categoría (función _listar_archivos_locales_por_categoria).
- Se llama a descargar_datasets_desde_drive(folder_id, cred_path, work_dir, sobrescribir_existentes=False, progress_cb=...).
  - Esta función descarga archivos nuevos desde Drive a subcarpetas bajo gdrive_import/ siguiendo FOLDER_TO_TIPO.
  - No sobrescribe archivos existentes por defecto (sobrescribir_existentes=False).
- Tras la descarga se vuelve a listar la carpeta para detectar archivos nuevos por categoría comparando antes/después.

Comportamiento importante:
- Solo se consideran archivos con extensiones válidas: .xlsx, .xls, .csv.

4) Paso 2/4 — Integración al CSV maestro (por categoría)

- Para cada categoría seleccionada, el pipeline intenta integrar los archivos nuevos detectados.
- Por cada archivo nuevo se llama a self.app.procesar_un_archivo(ruta, tipo_forzado=categoria, confirmar_encabezados=False, reemplazar_duplicados=True, show_ui_errors=False, permitir_año_manual=False).
  - procesar_un_archivo es responsable de validar encabezados/columnas, normalizar y anexar (o reemplazar duplicados) en el CSV maestro de la categoría.
- Si la integración de algún archivo falla, se levanta una excepción PipelineStageError para esa categoría y la categoría queda marcada como fallida (el pipeline continúa con las demás categorías).
- Si no hay archivos nuevos, se registra una advertencia y se continúa con la limpieza del CSV maestro existente.

5) Paso 3/4 — Limpieza y preprocesamiento del CSV maestro

- Se obtiene la ruta del CSV maestro con self.app._csv_path(categoria); si no existe, se marca error para la categoría.
- Se llama a preprocesar_csv_maestro(csv_path) (desde app/core/preprocessing_service.py). Esta función realiza:
  - Normalización de nombres de columnas.
  - Conversión de tipos (fechas, numéricos).
  - Detección y normalización del campo año con utilidades en year_utils.py.
  - Eliminación de duplicados y limpieza de valores nulos o ruido textual.
- El DataFrame resultante (df_limpio) se cuenta (filas resultantes) y se recarga el estado interno de la app (self.app.data.pop(categoria) y self.app._cargar_datos_completos(categoria)) para reflejar el CSV limpio en la UI.

6) Paso 4/4 — Inserción en MySQL

- Se llama a insertar_datos_csv(progress_cb=..., recreate=True) (en app/core/mysql_snies_setup.py).
  - recreate=True indica que la tabla de destino debe recrearse (el comportamiento exacto depende de la implementación interna).
- Si insertar_datos_csv devuelve False, la categoría se marca como fallida con etapa insercion_mysql.

7) Finalización por categoría

- Si todas las etapas anteriores completan sin lanzar errores para la categoría, esta se marca como ok y se registra en los logs.
- En caso de excepción no controlada, la categoría se marca como fallida con etapa="desconocida" y se guarda el detalle.

8) Resumen final

- Después de procesar todas las categorías seleccionadas, el pipeline muestra un resumen:
  - Si no hay fallos: messagebox informando éxito con el conteo de categorías procesadas.
  - Si hay fallos: messagebox con la lista de categorías con fallo, etapa y detalle.

---

## Manejo de errores y políticas

- Excepciones globales durante la descarga (descargar_datasets_desde_drive) lanzan PipelineStageError con categoria="GLOBAL" y detienen todo el pipeline.
- Errores por categoría (integración, limpieza, inserción) se encapsulan en PipelineStageError y se registran en resultados para mostrar un resumen; no detienen el procesamiento de las demás categorías.
- Logs detallados se imprimen en la caja de texto de la ventana y se envían como mensajes de estado a self.app.status_var.

---

## Archivos y rutas relevantes

- Carpeta de trabajo local: DATA_DIR/gdrive_import/ (creada si no existe).
- Fuente de mapeo Drive→Categoría: app/core/google_drive_loader.py (variable FOLDER_TO_TIPO).
- Integración de archivos: función procesar_un_archivo en la instancia app (vista de la UI principal).
- Limpieza: app/core/preprocessing_service.py::preprocesar_csv_maestro.
- Inserción en BD: app/core/mysql_snies_setup.py::insertar_datos_csv.

---

## Cómo ejecutar el pipeline

Desde la interfaz gráfica:

1. Abrir la aplicación (python main.py).
2. Abrir la ventana Pipeline automatico por categorias desde la UI principal.
3. Rellenar ID carpeta Drive y seleccionar Credenciales JSON.
4. Seleccionar las categorías y presionar Iniciar pipeline.

Ejecución programática (si se dispone de API interna):

- No hay un runner CLI expuesto explícito en el código mostrado; el pipeline está diseñado para lanzarse desde la UI. Para automatizarlo, se podría crear una rutina que instancie VentanaPipelineCategorias o extraiga la lógica de _ejecutar_pipeline a una función reutilizable.

---

## Consejos de depuración

- Revisar la caja de logs dentro de la ventana para mensajes temporales con prefijos [DRIVE], [PIPELINE], [MYSQL].
- Verificar permisos y validez del cred_path (archivo JSON) y que la API de Drive tenga acceso a la carpeta indicada.
- Comprobar que los archivos descargados tengan cabeceras válidas y extensiones permitidas.
- Si la inserción MySQL falla, revisar la configuración de conexión en mysql_snies_setup.py y logs de la base de datos.

---

Fin del documento.
