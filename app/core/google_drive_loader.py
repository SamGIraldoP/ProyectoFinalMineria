import os
import re
from typing import Callable, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Carpeta en Google Drive -> nombre de tipo usado por la app.
FOLDER_TO_TIPO = {
    "Estudiantes_admitidos": "Estudiantes admitidos",
    "Estudiantes_inscritos": "Estudiantes inscritos",
    "Estudiantes_matriculados": "Estudiantes matriculados",
    "Estudiantes_matriculados_en_primer_curso": "Estudiantes matriculados en primer curso",
    "Estudiantes_graduados": "Estudiantes graduados",
    "Docentes": "Docentes",
    "Administrativos": "Administrativos",
}


def _sanitize_filename(name: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
    return clean or "archivo"


def _build_drive_service(credentials_path: str):
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=creds)


def _list_children(service, parent_id: str):
    query = f"'{parent_id}' in parents and trashed = false"
    fields = "files(id, name, mimeType)"
    response = service.files().list(q=query, fields=fields, pageSize=1000).execute()
    return response.get("files", [])


def _download_drive_file(service, file_id: str, destination_path: str, progress_cb: Optional[Callable[[str], None]] = None) -> None:
    request = service.files().get_media(fileId=file_id)
    with open(destination_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        last_pct = -1
        while not done:
            status, done = downloader.next_chunk()
            if progress_cb and status:
                pct = int(status.progress() * 100)
                # Evitar ruido excesivo: mostrar cada 25% y al final.
                if pct in {25, 50, 75, 100} and pct != last_pct:
                    progress_cb(f"Descargando {os.path.basename(destination_path)}... {pct}%")
                    last_pct = pct


def _export_google_sheet(service, file_id: str, destination_path: str, progress_cb: Optional[Callable[[str], None]] = None) -> None:
    request = service.files().export_media(
        fileId=file_id,
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    with open(destination_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        last_pct = -1
        while not done:
            status, done = downloader.next_chunk()
            if progress_cb and status:
                pct = int(status.progress() * 100)
                if pct in {25, 50, 75, 100} and pct != last_pct:
                    progress_cb(f"Exportando Google Sheet {os.path.basename(destination_path)}... {pct}%")
                    last_pct = pct


def descargar_datasets_desde_drive(
    folder_id: str,
    credentials_path: str,
    work_dir: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, List[str]]:
    """Descarga archivos por tipo desde la carpeta datos_snies de Drive.

    Devuelve un diccionario tipo -> lista de archivos locales descargados.
    """
    os.makedirs(work_dir, exist_ok=True)
    if progress_cb:
        progress_cb("Inicializando cliente de Google Drive...")
    service = _build_drive_service(credentials_path)

    result: Dict[str, List[str]] = {tipo: [] for tipo in FOLDER_TO_TIPO.values()}
    if progress_cb:
        progress_cb("Listando carpetas dentro de datos_snies...")
    children = _list_children(service, folder_id)

    for child in children:
        folder_name = child.get("name", "")
        tipo = FOLDER_TO_TIPO.get(folder_name)
        if not tipo or child.get("mimeType") != "application/vnd.google-apps.folder":
            continue
        if progress_cb:
            progress_cb(f"Procesando carpeta {folder_name}...")

        tipo_dir = os.path.join(work_dir, folder_name)
        os.makedirs(tipo_dir, exist_ok=True)

        if progress_cb:
            progress_cb(f"Listando archivos de {folder_name}...")
        files = _list_children(service, child["id"])
        for drive_file in files:
            mime = drive_file.get("mimeType", "")
            original_name = _sanitize_filename(drive_file.get("name", "archivo"))

            if mime == "application/vnd.google-apps.folder":
                continue

            if mime == "application/vnd.google-apps.spreadsheet":
                file_name = f"{original_name}.xlsx"
                dest = os.path.join(tipo_dir, file_name)
                if progress_cb:
                    progress_cb(f"Exportando hoja {original_name} de {folder_name}...")
                _export_google_sheet(service, drive_file["id"], dest, progress_cb=progress_cb)
                result[tipo].append(dest)
                if progress_cb:
                    progress_cb(f"Archivo listo: {dest}")
                continue

            ext = os.path.splitext(original_name)[1].lower()
            if ext not in {".xlsx", ".xls", ".csv"}:
                # Saltar formatos no compatibles con el pipeline actual.
                if progress_cb:
                    progress_cb(f"Saltando archivo no compatible: {original_name}")
                continue

            dest = os.path.join(tipo_dir, original_name)
            if progress_cb:
                progress_cb(f"Descargando archivo {original_name} de {folder_name}...")
            _download_drive_file(service, drive_file["id"], dest, progress_cb=progress_cb)
            result[tipo].append(dest)
            if progress_cb:
                progress_cb(f"Archivo listo: {dest}")

    if progress_cb:
        total = sum(len(v) for v in result.values())
        progress_cb(f"Descarga finalizada. Archivos descargados: {total}")

    return result
