import json
import uuid
from io import BytesIO

import ufiles
from server.config import Settings


async def upload_ufile(
    file_bytes: BytesIO,
    user_id: uuid.UUID,
    meta_data: dict | None = None,
    file_upload_dir: str = "videogens",
):
    client = ufiles.AsyncUFiles(
        ufiles_base_url=Settings.UFILES_BASE_URL,
        usso_base_url=Settings.USSO_BASE_URL,
        api_key=Settings.UFILES_API_KEY,
    )

    return await client.upload_bytes(
        file_bytes,
        filename=f"{file_upload_dir}/{file_bytes.name}",
        public_permission=json.dumps({"permission": ufiles.PermissionEnum.READ}),
        user_id=str(user_id),
        meta_data=meta_data,
        timeout=None,
    )
