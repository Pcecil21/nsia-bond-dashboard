"""
Page 11: Document Library
Central repository for board governance documents, financial files, and contracts.
Supports local file uploads, external links, and Google Drive folder browsing.
"""
import streamlit as st
import json
import os
import re
import uuid
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_router import (
    analyze_document,
    detect_agent,
    get_api_key,
    ANTHROPIC_AVAILABLE,
    AGENT_REGISTRY,
)

from utils.auth import require_auth

st.set_page_config(page_title="Document Library | NSIA", layout="wide", page_icon=":ice_hockey:")

require_auth()

from utils.theme import FONT_COLOR, inject_css

inject_css()

# ── Constants ────────────────────────────────────────────────────────────
CATEGORIES = ["Board Governance", "Financial Documents", "Contracts & Agreements"]
ALLOWED_EXTENSIONS = ["pdf", "xlsx", "csv", "docx", "png", "jpg"]
MAX_FILE_SIZE_MB = 50
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "documents")
CATALOG_PATH = os.path.join(DATA_DIR, "catalog.json")
DRIVE_CONFIG_PATH = os.path.join(DATA_DIR, "drive_config.json")

# ── File type icons ──────────────────────────────────────────────────────
MIME_ICONS = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
    "application/vnd.google-apps.spreadsheet": "Sheet",
    "application/vnd.google-apps.document": "Doc",
    "application/vnd.google-apps.presentation": "Slides",
    "application/vnd.google-apps.folder": "Folder",
    "text/csv": "CSV",
    "image/png": "PNG",
    "image/jpeg": "JPG",
}


# ── Helpers ──────────────────────────────────────────────────────────────
def load_catalog() -> list[dict]:
    if not os.path.exists(CATALOG_PATH):
        return []
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)


def save_catalog(catalog: list[dict]):
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)


def safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = name.replace("\x00", "")
    name = re.sub(r"[^\w.\-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name if name else "unnamed_file"


def _has_drive_secrets() -> bool:
    """Check if Google Drive secrets are configured in st.secrets."""
    try:
        return bool(st.secrets.get("google_drive", {}).get("folder_id"))
    except Exception:
        return False


def load_drive_config() -> dict | None:
    # Prefer st.secrets (for Streamlit Cloud), fall back to local config file
    if _has_drive_secrets():
        return {
            "folder_id": st.secrets["google_drive"]["folder_id"],
            "source": "secrets",
        }
    if not os.path.exists(DRIVE_CONFIG_PATH):
        return None
    with open(DRIVE_CONFIG_PATH, "r") as f:
        config = json.load(f)
    if not config.get("folder_id"):
        return None
    creds_path = config.get("credentials_file", "")
    if creds_path and not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), creds_path)
    config["_resolved_creds"] = creds_path
    config["source"] = "local"
    return config


def _get_drive_creds_from_secrets():
    """Build OAuth credentials from st.secrets (for cloud deployment)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    sec = st.secrets["google_drive"]
    creds = Credentials(
        token=None,
        refresh_token=sec["refresh_token"],
        token_uri=sec["token_uri"],
        client_id=sec["client_id"],
        client_secret=sec["client_secret"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    creds.refresh(Request())
    return creds


def _get_drive_creds_from_local():
    """Get OAuth credentials from local token.json file."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    token_path = os.path.join(DATA_DIR, "token.json")

    if not os.path.exists(token_path):
        return None

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            return creds
        except Exception:
            return None

    return None


def get_drive_credentials(config: dict):
    """Get credentials from secrets or local token, depending on config source."""
    if config.get("source") == "secrets":
        return _get_drive_creds_from_secrets()
    return _get_drive_creds_from_local()


@st.cache_data(ttl=300, show_spinner=False)
def list_drive_files(folder_id: str, _cache_key: str) -> list[dict]:
    """List files in a Google Drive folder."""
    from googleapiclient.discovery import build

    config = load_drive_config()
    if not config:
        return []

    creds = get_drive_credentials(config)
    if not creds:
        return []

    service = build("drive", "v3", credentials=creds)

    all_files = []
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, size)",
            orderBy="modifiedTime desc",
            pageSize=100,
            pageToken=page_token,
        ).execute()
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return all_files


GOOGLE_EXPORT_MIMES = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


@st.cache_data(ttl=600, show_spinner=False)
def download_drive_file(file_id: str, mime_type: str) -> tuple[bytes, str] | None:
    """Download a file from Google Drive. Returns (bytes, filename_suffix) or None."""
    from googleapiclient.discovery import build
    import io

    config = load_drive_config()
    if not config:
        return None
    creds = get_drive_credentials(config)
    if not creds:
        return None

    service = build("drive", "v3", credentials=creds)

    if mime_type in GOOGLE_EXPORT_MIMES:
        export_mime, ext = GOOGLE_EXPORT_MIMES[mime_type]
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    else:
        request = service.files().get_media(fileId=file_id)

    from googleapiclient.http import MediaIoBaseDownload
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()


def is_previewable(mime_type: str) -> bool:
    """Check if a file can be previewed inline via Google's viewer."""
    return mime_type != "application/vnd.google-apps.folder"


def format_file_size(size_str: str | None) -> str:
    if not size_str:
        return "—"
    size = int(size_str)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def format_drive_date(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    return iso_str[:10]


# ── Header ───────────────────────────────────────────────────────────────
catalog = load_catalog()

st.title("Document Library")
doc_count = len(catalog)
st.markdown(
    f"Board documents, financial files, and contracts &nbsp; "
    f'<span style="background:#0f3460;padding:2px 10px;border-radius:10px;'
    f'font-size:0.8rem;color:#a8b2d1;">{doc_count} cataloged</span>',
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Sidebar Filters ──────────────────────────────────────────────────────
st.sidebar.markdown("### Document Filters")
category_filter = st.sidebar.selectbox(
    "Category",
    ["All"] + CATEGORIES,
    index=0,
)
search_query = st.sidebar.text_input("Search", placeholder="Filter by name or description...")

# ── Google Drive Section ─────────────────────────────────────────────────
drive_config = load_drive_config()

if drive_config:
    st.markdown("### Google Drive")
    token_path = os.path.join(DATA_DIR, "token.json")
    has_token = os.path.exists(token_path)

    # Check if we have credentials (secrets or local token)
    has_creds = drive_config.get("source") == "secrets" or os.path.exists(token_path)

    if not has_creds:
        st.warning("Google Drive is not connected. Run the app locally first to authenticate.")
        drive_files = []
    else:
        try:
            # Navigate into subfolders if user clicked into one
            if "drive_path" in st.session_state and st.session_state.drive_path:
                current_folder = st.session_state.drive_path[-1][0]
            else:
                current_folder = drive_config["folder_id"]
            cache_key = drive_config.get("source", "local")
            drive_files = list_drive_files(current_folder, cache_key)
        except Exception as e:
            drive_files = []
            st.error(f"Could not load Google Drive files: {e}")

    if drive_files:
        # Track folder navigation
        if "drive_path" not in st.session_state:
            st.session_state.drive_path = []  # list of (folder_id, folder_name)

        # Apply search filter to Drive files
        if search_query:
            q = search_query.lower()
            drive_files = [f for f in drive_files if q in f["name"].lower()]

        # Sort: folders first, then files by date
        folders = [f for f in drive_files if f.get("mimeType") == "application/vnd.google-apps.folder"]
        files = [f for f in drive_files if f.get("mimeType") != "application/vnd.google-apps.folder"]
        drive_files = folders + files

        if drive_files:
            # Navigation breadcrumb + refresh
            nav_col, refresh_col = st.columns([5, 1])
            with nav_col:
                breadcrumb = "**Root**"
                if st.session_state.drive_path:
                    if st.button("← Back", key="drive_back"):
                        st.session_state.drive_path.pop()
                        list_drive_files.clear()
                        st.rerun()
                    path_names = " / ".join(p[1] for p in st.session_state.drive_path)
                    breadcrumb = f"Root / {path_names}"
                st.caption(breadcrumb)
            with refresh_col:
                if st.button("Refresh", key="drive_refresh"):
                    list_drive_files.clear()
                    st.rerun()

            for f in drive_files:
                is_folder = f.get("mimeType") == "application/vnd.google-apps.folder"
                mime = f.get("mimeType", "")
                file_type = MIME_ICONS.get(mime, "File")
                type_color = "#fcb900" if is_folder else "#0984e3"

                col_info, col_meta, col_action = st.columns([4, 2, 1])

                with col_info:
                    st.markdown(
                        f'**{f["name"]}** &nbsp; '
                        f'<span style="background:{type_color};padding:1px 8px;border-radius:8px;'
                        f'font-size:0.75rem;color:#fff;">{file_type}</span>',
                        unsafe_allow_html=True,
                    )

                with col_meta:
                    size_str = format_file_size(f.get("size"))
                    date_str = format_drive_date(f.get("modifiedTime"))
                    st.caption(f"{date_str} &nbsp; | &nbsp; {size_str}")

                with col_action:
                    if is_folder:
                        if st.button("Open", key=f"drive_{f['id']}"):
                            st.session_state.drive_path.append((f["id"], f["name"]))
                            list_drive_files.clear()
                            st.rerun()
                    elif not is_folder:
                        btn_cols = st.columns(2)
                        # Download button
                        if btn_cols[0].button("Download", key=f"dl_{f['id']}"):
                            st.session_state[f"_downloading_{f['id']}"] = True
                        # Preview button for PDFs and images
                        if is_previewable(mime):
                            if btn_cols[1].button("Preview", key=f"pv_{f['id']}"):
                                st.session_state[f"_preview_{f['id']}"] = not st.session_state.get(f"_preview_{f['id']}", False)

                # Handle download
                if st.session_state.get(f"_downloading_{f.get('id')}"):
                    with st.spinner("Downloading..."):
                        data = download_drive_file(f["id"], mime)
                    if data:
                        ext = GOOGLE_EXPORT_MIMES.get(mime, (None, ""))[1] if mime in GOOGLE_EXPORT_MIMES else ""
                        dl_name = f["name"] + ext if ext and not f["name"].endswith(ext) else f["name"]
                        st.download_button(
                            f"Save {dl_name}",
                            data=data,
                            file_name=dl_name,
                            key=f"save_{f['id']}",
                        )
                    else:
                        st.error("Could not download file.")
                    st.session_state.pop(f"_downloading_{f['id']}", None)

                # Handle preview — use Google's own viewer for proper formatting
                if st.session_state.get(f"_preview_{f.get('id')}"):
                    preview_url = f"https://drive.google.com/file/d/{f['id']}/preview"
                    st.markdown(
                        f'<iframe src="{preview_url}" '
                        f'width="100%" height="700" style="border:none;border-radius:8px;"></iframe>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    '<div style="border-bottom:1px solid rgba(168,178,209,0.1);margin:4px 0 8px;"></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No Drive files match your search.")
    elif not drive_files and not st.session_state.get("_drive_error"):
        st.info("Google Drive folder is empty.")

    st.markdown("---")

# ── Cataloged Documents ──────────────────────────────────────────────────
filtered = catalog
if category_filter != "All":
    filtered = [d for d in filtered if d["category"] == category_filter]
if search_query:
    q = search_query.lower()
    filtered = [
        d for d in filtered
        if q in d["name"].lower() or q in (d.get("description") or "").lower()
    ]

if catalog:
    st.markdown("### Cataloged Documents")

if not filtered and catalog:
    st.info("No cataloged documents match your filters.")
elif not filtered and not catalog:
    pass  # no header shown, skip
else:
    for doc in sorted(filtered, key=lambda d: d.get("date_added", ""), reverse=True):
        col_info, col_actions = st.columns([4, 1])

        with col_info:
            cat_color = {"Board Governance": "#00b894", "Financial Documents": "#0984e3", "Contracts & Agreements": "#6c5ce7"}.get(doc["category"], FONT_COLOR)
            st.markdown(
                f'**{doc["name"]}** &nbsp; '
                f'<span style="background:{cat_color};padding:1px 8px;border-radius:8px;'
                f'font-size:0.75rem;color:#fff;">{doc["category"]}</span>',
                unsafe_allow_html=True,
            )
            meta_parts = []
            if doc.get("description"):
                meta_parts.append(doc["description"])
            meta_parts.append(f'Added {doc.get("date_added", "—")}')
            if doc.get("uploaded_by"):
                meta_parts.append(f'by {doc["uploaded_by"]}')
            ai_class = doc.get("ai_classification")
            if ai_class and ai_class.get("agent_name"):
                meta_parts.append(f'AI: {ai_class["agent_name"]}')
            st.caption(" | ".join(meta_parts))

        with col_actions:
            action_cols = st.columns(2)
            if doc["storage"] == "local":
                file_path = os.path.join(DATA_DIR, doc["category"], doc.get("filename", ""))
                if os.path.exists(file_path):
                    with open(file_path, "rb") as fp:
                        action_cols[0].download_button(
                            "Download",
                            data=fp.read(),
                            file_name=doc.get("filename", doc["name"]),
                            key=f"dl_{doc['id']}",
                        )
                else:
                    action_cols[0].warning("Missing")
            elif doc["storage"] == "external" and doc.get("external_url"):
                action_cols[0].link_button("Open", doc["external_url"])

            if action_cols[1].button("Delete", key=f"del_{doc['id']}", type="secondary"):
                st.session_state[f"confirm_delete_{doc['id']}"] = True

            if st.session_state.get(f"confirm_delete_{doc['id']}"):
                st.warning(f"Delete **{doc['name']}**? This cannot be undone.")
                confirm_cols = st.columns(2)
                if confirm_cols[0].button("Yes, delete", key=f"yes_{doc['id']}", type="primary"):
                    if doc["storage"] == "local" and doc.get("filename"):
                        fpath = os.path.join(DATA_DIR, doc["category"], doc["filename"])
                        if os.path.exists(fpath):
                            os.remove(fpath)
                    catalog = [d for d in catalog if d["id"] != doc["id"]]
                    save_catalog(catalog)
                    st.session_state.pop(f"confirm_delete_{doc['id']}", None)
                    st.rerun()
                if confirm_cols[1].button("Cancel", key=f"cancel_{doc['id']}"):
                    st.session_state.pop(f"confirm_delete_{doc['id']}", None)
                    st.rerun()

        st.markdown("---")

# ── Upload Section ───────────────────────────────────────────────────────
st.markdown("### Add Documents")

tab_upload, tab_link = st.tabs(["Upload File", "Add External Link"])

with tab_upload:
    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=ALLOWED_EXTENSIONS,
            help=f"Max {MAX_FILE_SIZE_MB}MB. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )
        u_name = st.text_input("Display Name (optional)", help="Leave blank to use filename")
        u_category = st.selectbox("Category", CATEGORIES, key="upload_category")
        u_description = st.text_input("Description")
        u_uploaded_by = st.text_input("Uploaded By", value="Pete Ceci")

        submitted = st.form_submit_button("Upload", type="primary")
        if submitted and uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"File exceeds {MAX_FILE_SIZE_MB}MB limit.")
            else:
                filename = safe_filename(uploaded_file.name)
                display_name = u_name.strip() if u_name.strip() else uploaded_file.name

                cat_dir = os.path.join(DATA_DIR, u_category)
                os.makedirs(cat_dir, exist_ok=True)

                dest_path = os.path.join(cat_dir, filename)
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{uuid.uuid4().hex[:6]}{ext}"
                    dest_path = os.path.join(cat_dir, filename)

                with open(dest_path, "wb") as f:
                    f.write(file_bytes)

                # AI auto-classification
                ai_tags = None
                if ANTHROPIC_AVAILABLE and get_api_key():
                    ext = os.path.splitext(filename)[1].lower().lstrip(".")
                    preview = ""
                    if ext in ("csv", "txt"):
                        try:
                            preview = file_bytes.decode("utf-8", errors="replace")[:2000]
                        except Exception:
                            pass
                    elif ext in ("xlsx", "xls"):
                        try:
                            import pandas as pd
                            import io
                            xls = pd.ExcelFile(io.BytesIO(file_bytes))
                            sheets_preview = []
                            for sn in xls.sheet_names[:3]:
                                df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sn, nrows=10)
                                sheets_preview.append(f"Sheet: {sn}\n{df.to_csv(index=False)}")
                            preview = "\n".join(sheets_preview)
                        except Exception:
                            pass

                    detected_agent = detect_agent(filename, preview)
                    agent_name = AGENT_REGISTRY.get(detected_agent, {}).get("name", "")
                    ai_tags = {
                        "detected_agent": detected_agent,
                        "agent_name": agent_name,
                        "document_type": AGENT_REGISTRY.get(detected_agent, {}).get("description", ""),
                    }

                entry = {
                    "id": str(uuid.uuid4()),
                    "name": display_name,
                    "category": u_category,
                    "description": u_description,
                    "uploaded_by": u_uploaded_by,
                    "date_added": date.today().isoformat(),
                    "storage": "local",
                    "filename": filename,
                    "external_url": None,
                    "ai_classification": ai_tags,
                }

                catalog.append(entry)
                save_catalog(catalog)
                if ai_tags:
                    st.success(
                        f"Uploaded **{display_name}** to {u_category}. "
                        f"AI classified as: **{ai_tags['agent_name']}** document."
                    )
                else:
                    st.success(f"Uploaded **{display_name}** to {u_category}.")
                st.rerun()
        elif submitted and uploaded_file is None:
            st.warning("Please select a file to upload.")

with tab_link:
    with st.form("link_form", clear_on_submit=True):
        l_name = st.text_input("Document Name")
        l_category = st.selectbox("Category", CATEGORIES, key="link_category")
        l_description = st.text_input("Description", key="link_desc")
        l_url = st.text_input("SharePoint / OneDrive / Google Drive URL")
        l_uploaded_by = st.text_input("Added By", value="Pete Ceci", key="link_by")

        link_submitted = st.form_submit_button("Add Link", type="primary")
        if link_submitted:
            if not l_name.strip():
                st.warning("Please enter a document name.")
            elif not l_url.strip():
                st.warning("Please enter a URL.")
            else:
                entry = {
                    "id": str(uuid.uuid4()),
                    "name": l_name.strip(),
                    "category": l_category,
                    "description": l_description,
                    "uploaded_by": l_uploaded_by,
                    "date_added": date.today().isoformat(),
                    "storage": "external",
                    "filename": None,
                    "external_url": l_url.strip(),
                }
                catalog.append(entry)
                save_catalog(catalog)
                st.success(f"Added external link **{l_name.strip()}**.")
                st.rerun()
