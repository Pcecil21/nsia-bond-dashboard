import argparse
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_FOLDER_ID = "1r0s755LUwwE_s9We3rmtjxad8B5j8xaI"
DEFAULT_DEST = r"C:\Users\pceci\Claude\Home Projects\nsia-bond-dashboard"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"

EXPORT_MAP = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", name).strip()
    return cleaned or "unnamed"


def load_state(state_path: Path) -> Dict[str, str]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state_path: Path, state: Dict[str, str]) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def authenticate(credentials_path: Path, token_path: Path):
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


def list_files(service, folder_id: str):
    query = f"'{folder_id}' in parents and trashed=false"
    fields = "nextPageToken, files(id, name, mimeType, modifiedTime)"

    items = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields=fields,
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageSize=1000,
            )
            .execute()
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return items


def resolve_target_name(dest_dir: Path, base_name: str, file_id: str) -> Path:
    target = dest_dir / base_name
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    fallback = f"{stem}__{file_id[:8]}{suffix}"
    return dest_dir / fallback


def build_download_request(service, file_item: dict) -> Tuple[object, str]:
    file_id = file_item["id"]
    mime_type = file_item.get("mimeType", "")
    name = sanitize_filename(file_item.get("name", file_id))

    if mime_type in EXPORT_MAP:
        export_mime, extension = EXPORT_MAP[mime_type]
        if not name.lower().endswith(extension):
            name += extension
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        return request, name

    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    return request, name


def download_file(service, file_item: dict, dest_dir: Path) -> Path:
    request, suggested_name = build_download_request(service, file_item)
    output_path = resolve_target_name(dest_dir, suggested_name, file_item["id"])

    with io.BytesIO() as buffer:
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        output_path.write_bytes(buffer.getvalue())

    return output_path


def sync_folder_recursive(service, folder_id: str, dest_dir: Path, state: Dict[str, str], current: Dict[str, str]) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    items = list_files(service, folder_id)

    for item in items:
        if item.get("mimeType") == GOOGLE_FOLDER_MIME:
            subfolder_name = sanitize_filename(item.get("name", item["id"]))
            subfolder_dest = dest_dir / subfolder_name
            logging.info("Entering subfolder: %s -> %s", item.get("name"), subfolder_dest)
            sync_folder_recursive(service, item["id"], subfolder_dest, state, current)
            continue

        file_id = item["id"]
        modified = item.get("modifiedTime", "")
        current[file_id] = modified

        if state.get(file_id) == modified:
            continue

        saved = download_file(service, item, dest_dir)
        logging.info("Synced: %s -> %s", item.get("name", file_id), saved)


def sync_once(service, folder_id: str, dest_dir: Path, state_path: Path) -> None:
    state = load_state(state_path)
    current = {}

    sync_folder_recursive(service, folder_id, dest_dir, state, current)

    save_state(state_path, current)


def parse_args():
    parser = argparse.ArgumentParser(description="Mirror Google Drive folder files to a local folder.")
    parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID, help="Google Drive folder ID")
    parser.add_argument("--dest", default=DEFAULT_DEST, help="Local destination folder")
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to OAuth credentials JSON from Google Cloud",
    )
    parser.add_argument("--token", default="token.json", help="Path to OAuth token cache")
    parser.add_argument("--state", default="sync_state.json", help="Path to sync state JSON")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    dest_dir = Path(args.dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    script_dir = Path(__file__).resolve().parent
    credentials_path = (script_dir / args.credentials).resolve()
    token_path = (script_dir / args.token).resolve()
    state_path = (script_dir / args.state).resolve()

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Missing credentials file: {credentials_path}. "
            "Create OAuth Desktop credentials in Google Cloud and save as credentials.json."
        )

    service = authenticate(credentials_path, token_path)

    logging.info("Watching Google Drive folder %s", args.folder_id)
    logging.info("Mirroring to %s", dest_dir)

    while True:
        try:
            sync_once(service, args.folder_id, dest_dir, state_path)
        except HttpError as err:
            logging.error("Google Drive API error: %s", err)
        except Exception as err:
            logging.error("Unexpected error: %s", err)

        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
