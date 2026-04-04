import io
import os
from typing import Dict, List, Optional

from pypdf import PdfReader
from docx import Document

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except Exception:
    Credentials = None
    build = None
    MediaIoBaseDownload = None


GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _get_config_value(name: str, default=None):
    try:
        import config  # type: ignore

        return getattr(config, name, default)
    except Exception:
        return default


def _get_credentials_file() -> Optional[str]:
    return (
        _get_config_value("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )


def _get_folder_id() -> Optional[str]:
    return _get_config_value("GOOGLE_DRIVE_FOLDER_ID") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def get_drive_service():
    if Credentials is None or build is None:
        raise RuntimeError("Bibliotecas do Google Drive não instaladas.")

    credentials_file = _get_credentials_file()
    if not credentials_file or not os.path.exists(credentials_file):
        raise FileNotFoundError(
            "Arquivo de credenciais do Google não encontrado. "
            "Defina GOOGLE_SERVICE_ACCOUNT_FILE ou GOOGLE_APPLICATION_CREDENTIALS."
        )

    credentials = Credentials.from_service_account_file(
        credentials_file,
        scopes=GOOGLE_DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def list_recent_files(
    folder_id: Optional[str] = None,
    page_size: int = 20,
) -> List[Dict]:
    """
    Lista arquivos recentes do Drive.
    Se folder_id não for informado, tenta do config/env.
    """
    service = get_drive_service()
    folder_id = folder_id or _get_folder_id()

    query_parts = ["trashed = false"]
    if folder_id:
        query_parts.append(f"'{folder_id}' in parents")

    query = " and ".join(query_parts)

    response = (
        service.files()
        .list(
            q=query,
            pageSize=page_size,
            fields=(
                "files(id,name,mimeType,modifiedTime,webViewLink,webContentLink,size)"
            ),
            orderBy="modifiedTime desc",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    return response.get("files", [])


def download_file_bytes(file_id: str) -> bytes:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.seek(0)
    return fh.read()


def export_google_workspace_file(file_id: str, mime_type: str) -> bytes:
    """
    Exporta docs nativos do Google para formatos processáveis.
    """
    service = get_drive_service()

    export_map = {
        "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "application/pdf",
    }

    export_mime = export_map.get(mime_type)
    if not export_mime:
        raise ValueError(f"Tipo Google Workspace não suportado: {mime_type}")

    request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.seek(0)
    return fh.read()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text).strip()


def extract_text_from_txt(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return file_bytes.decode(encoding).strip()
        except Exception:
            continue
    return ""


def extract_text_from_csv(file_bytes: bytes) -> str:
    return extract_text_from_txt(file_bytes)


def extract_text_from_file(file_id: str, mime_type: str) -> str:
    """
    Faz download/export e extrai texto.
    """
    google_workspace_types = {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
    }

    if mime_type in google_workspace_types:
        file_bytes = export_google_workspace_file(file_id, mime_type)

        if mime_type == "application/vnd.google-apps.document":
            return extract_text_from_docx(file_bytes)

        if mime_type == "application/vnd.google-apps.spreadsheet":
            return extract_text_from_csv(file_bytes)

        if mime_type == "application/vnd.google-apps.presentation":
            return extract_text_from_pdf(file_bytes)

    file_bytes = download_file_bytes(file_id)

    if mime_type == "application/pdf":
        return extract_text_from_pdf(file_bytes)

    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return extract_text_from_docx(file_bytes)

    if mime_type in ("text/plain", "text/markdown"):
        return extract_text_from_txt(file_bytes)

    if mime_type in ("text/csv", "application/csv"):
        return extract_text_from_csv(file_bytes)

    # fallback: tenta texto puro
    text = extract_text_from_txt(file_bytes)
    if text:
        return text

    return ""


def get_file_metadata(file_id: str) -> Dict:
    service = get_drive_service()
    return (
        service.files()
        .get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime,webViewLink,webContentLink,size",
            supportsAllDrives=True,
        )
        .execute()
    )


# aliases de compatibilidade
def get_recent_drive_files(page_size: int = 20) -> List[Dict]:
    return list_recent_files(page_size=page_size)


def download_drive_text(file_id: str, mime_type: str) -> str:
    return extract_text_from_file(file_id, mime_type)
