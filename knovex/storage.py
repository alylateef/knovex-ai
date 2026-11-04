import hashlib
import os
import re
from pathlib import Path
from typing import Tuple
from fastapi import HTTPException, UploadFile, status

from knovex.config import get_settings

settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_MIME_TYPES = {"application/pdf", "text/plain", "application/octet-stream"}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and remove problematic characters."""
    base_name = os.path.basename(filename)
    clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base_name)
    return clean_name


def get_tenant_upload_dir(tenant_id: str) -> Path:
    """Get and ensure tenant-isolated upload directory."""
    tenant_dir = settings.UPLOAD_DIR.resolve() / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return tenant_dir


async def save_uploaded_file(tenant_id: str, file: UploadFile) -> Tuple[Path, str, int, str, str]:
    """
    Validate, sanitize and save an uploaded file inside the tenant's upload directory.
    Returns: (saved_file_path, sanitized_filename, file_size, mime_type, sha256_hash)
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty"
        )

    clean_filename = sanitize_filename(file.filename)
    file_ext = Path(clean_filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{file_ext}'. Allowed types: PDF (.pdf), Text (.txt)"
        )

    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES and not file_ext in {".txt", ".pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{mime_type}' for document upload"
        )

    tenant_dir = get_tenant_upload_dir(tenant_id)
    target_path = (tenant_dir / clean_filename).resolve()

    # Verify that target path does not escape tenant_dir (prevent path traversal)
    if not str(target_path).startswith(str(tenant_dir)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path detected (directory traversal attempt rejected)"
        )

    # Stream write, enforce maximum file size, and compute SHA-256
    bytes_written = 0
    hasher = hashlib.sha256()
    with open(target_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB buffer
            bytes_written += len(chunk)
            if bytes_written > settings.MAX_UPLOAD_SIZE_BYTES:
                f.close()
                if target_path.exists():
                    target_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024):.1f}MB"
                )
            hasher.update(chunk)
            f.write(chunk)

    file_hash = hasher.hexdigest()
    return target_path, clean_filename, bytes_written, mime_type, file_hash

