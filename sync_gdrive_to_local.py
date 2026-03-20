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
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
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


# ---------------------------------------------------------------------------
# Upload / folder-creation helpers
# ---------------------------------------------------------------------------

def find_or_create_folder(service, parent_id: str, folder_name: str) -> str:
    """Find a subfolder by name under parent_id, or create it. Returns folder ID."""
    query = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='{GOOGLE_FOLDER_MIME}' "
        f"and name='{folder_name}'"
    )
    results = service.files().list(
        q=query, fields="files(id, name)", pageSize=1,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": GOOGLE_FOLDER_MIME,
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    logging.info("Created Drive folder: %s (id=%s)", folder_name, folder["id"])
    return folder["id"]


def find_or_create_folder_path(service, root_id: str, path_parts: list) -> str:
    """Walk/create a nested folder path under root_id. Returns the leaf folder ID."""
    current_id = root_id
    for part in path_parts:
        current_id = find_or_create_folder(service, current_id, part)
    return current_id


def upload_file(service, local_path: Path, parent_folder_id: str) -> str:
    """Upload a local file to a Drive folder. Returns the new file ID."""
    import mimetypes
    mime_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

    metadata = {
        "name": local_path.name,
        "parents": [parent_folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
    uploaded = service.files().create(
        body=metadata, media_body=media, fields="id, name",
    ).execute()
    logging.info("Uploaded: %s -> Drive (id=%s)", local_path.name, uploaded["id"])
    return uploaded["id"]


def upload_folder(service, local_dir: Path, parent_folder_id: str) -> None:
    """Upload all files in a local directory to a Drive folder (non-recursive)."""
    for item in sorted(local_dir.iterdir()):
        if item.is_file() and not item.name.startswith("."):
            upload_file(service, item, parent_folder_id)


def parse_args():
    parser = argparse.ArgumentParser(description="Sync files between Google Drive and local folder.")
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # Default: sync (pull from Drive)
    sync_parser = sub.add_parser("sync", help="Pull files from Google Drive to local folder")
    sync_parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID, help="Google Drive folder ID")
    sync_parser.add_argument("--dest", default=DEFAULT_DEST, help="Local destination folder")
    sync_parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")

    # Upload: push local files to Drive
    upload_parser = sub.add_parser("upload", help="Upload local files to Google Drive")
    upload_parser.add_argument("local_path", help="Local file or folder to upload")
    upload_parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID, help="Target Drive folder ID")
    upload_parser.add_argument("--drive-path", default="", help="Subfolder path in Drive (e.g. 'Board Packages/2026-02-February')")

    # Common args on each subparser
    for p in [sync_parser, upload_parser]:
        p.add_argument("--credentials", default="credentials.json", help="Path to OAuth credentials JSON")
        p.add_argument("--token", default="token.json", help="Path to OAuth token cache")
        p.add_argument("--state", default="sync_state.json", help="Path to sync state JSON")

    args = parser.parse_args()
    # Default to sync if no command given
    if args.command is None:
        args.command = "sync"
        args.folder_id = DEFAULT_FOLDER_ID
        args.dest = DEFAULT_DEST
        args.interval = 30
    return args


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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

    if args.command == "upload":
        local_path = Path(args.local_path).expanduser().resolve()
        if not local_path.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")

        # Navigate to (or create) the target subfolder in Drive
        target_id = args.folder_id
        if args.drive_path:
            path_parts = [p.strip() for p in args.drive_path.replace("\\", "/").split("/") if p.strip()]
            target_id = find_or_create_folder_path(service, target_id, path_parts)

        if local_path.is_dir():
            upload_folder(service, local_path, target_id)
        else:
            upload_file(service, local_path, target_id)

        logging.info("Upload complete.")
        return

    # Default: sync (pull from Drive)
    dest_dir = Path(args.dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

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
