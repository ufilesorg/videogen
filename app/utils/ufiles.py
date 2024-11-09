import os
import uuid
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path

import aiofiles
import aiohttp
import json_advanced as json
import singleton
from fastapi_mongo_base.schemas import CoreEntitySchema
from pydantic import BaseModel
from usso.async_session import AsyncUssoSession


class PermissionEnum(int, Enum):
    NONE = 0
    READ = 10
    WRITE = 20
    MANAGE = 30
    DELETE = 40
    OWNER = 100


class PermissionSchema(CoreEntitySchema):
    permission: PermissionEnum = PermissionEnum.NONE

    @property
    def read(self):
        return self.permission >= PermissionEnum.READ

    @property
    def write(self):
        return self.permission >= PermissionEnum.WRITE

    @property
    def manage(self):
        return self.permission >= PermissionEnum.MANAGE

    @property
    def delete(self):
        return self.permission >= PermissionEnum.DELETE

    @property
    def owner(self):
        return self.permission >= PermissionEnum.OWNER


class Permission(PermissionSchema):
    user_id: uuid.UUID


class UFileItem(BaseModel):
    uid: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    meta_data: dict | None = None
    user_id: uuid.UUID
    business_name: str

    s3_key: str | None = None

    parent_id: uuid.UUID | None = None
    is_directory: bool = False

    root_url: str | None = None
    url: str | None = None

    filehash: str | None = None
    filename: str

    content_type: str = "image/webp"
    size: int = 4096
    deleted_at: datetime | None = None

    permissions: list[Permission] = []
    public_permission: PermissionSchema = PermissionSchema()


class AsyncUFiles(metaclass=singleton.Singleton):
    def __init__(self):
        self.refresh_token = os.getenv("USSO_REFRESH_TOKEN")
        self.refresh_url = os.getenv("USSO_REFRESH_URL")
        self.base_url = os.getenv("UFILES_URL")
        self.upload_url = f"{self.base_url}/upload"

    async def upload_file(self, filepath: Path, **kwargs) -> UFileItem:
        if not filepath.exists():
            raise FileNotFoundError(f"File {filepath} not found")

        async with AsyncUssoSession(self.refresh_url, self.refresh_token) as client:
            return await self.upload_file_session(client, filepath, **kwargs)

    async def upload_file_session(
        self, client: aiohttp.ClientSession, filepath: Path, **kwargs
    ) -> UFileItem:
        async with aiofiles.open(filepath, "rb") as f:
            file_size = os.path.getsize(filepath)
            if file_size > 1024 * 1024 * 100:
                raise ValueError("File size is too large")

            async with client.post(
                self.upload_url,
                data={"file": await f.read()},
            ) as response:
                response.raise_for_status()
                return UFileItem(**await response.json())

    async def upload_bytes(self, file_bytes: BytesIO, **kwargs) -> UFileItem:
        async with AsyncUssoSession(self.refresh_url, self.refresh_token) as client:
            return await self.upload_bytes_session(client, file_bytes, **kwargs)

    async def upload_bytes_session(
        self, client: aiohttp.ClientSession, file_bytes: BytesIO, **kwargs
    ) -> UFileItem:
        data = aiohttp.FormData()
        data.add_field("file", file_bytes, filename=kwargs.get("filename", "file"))
        for key, value in kwargs.items():
            if value is not None:
                if isinstance(value, dict) or isinstance(value, list):
                    value = json.dumps(value)
                data.add_field(key, value)
        async with client.post(self.upload_url, data=data) as response:
            response.raise_for_status()
            return UFileItem(**await response.json())
