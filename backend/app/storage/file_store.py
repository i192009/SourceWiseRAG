import uuid
from pathlib import Path
import aiofiles
from fastapi import UploadFile

from backend.app.core.settings import UPLOAD_DIR
from backend.app.utils.text import sanitize_filename


async def save_upload_file(file: UploadFile) -> tuple[str, str, int]:
    safe_name = sanitize_filename(file.filename or "uploaded_file")
    source_id = str(uuid.uuid4())
    dest_path = Path(UPLOAD_DIR) / f"{source_id}__{safe_name}"

    size = 0
    async with aiofiles.open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            await out.write(chunk)

    await file.close()
    return source_id, str(dest_path), size
