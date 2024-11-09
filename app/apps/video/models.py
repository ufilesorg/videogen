import asyncio
import logging

from fastapi_mongo_base.models import OwnedEntity
from server.config import Settings

from .schemas import VideoSchema


class Video(VideoSchema, OwnedEntity):
    class Settings:
        indexes = OwnedEntity.Settings.indexes

    @property
    def item_url(self):
        return f"{Settings.root_url}/v1/apps/video/{self.uid}"

    @property
    def webhook_url(self):
        return f"{self.item_url}/webhook"

    async def start_processing(self):
        from apps.video.services import video_request
        await video_request(self)

    async def retry(self, message: str, max_retries: int = 5):
        self.meta_data = self.meta_data or {}
        retry_count = self.meta_data.get("retry_count", 0)

        if retry_count < max_retries:
            self.meta_data["retry_count"] = retry_count + 1
            await self.save_report(
                f"Retry {self.uid} {self.meta_data.get('retry_count')}", emit=False
            )
            await self.save_and_emit()
            asyncio.create_task(self.start_processing())
            logging.info(f"Retry {retry_count} {self.uid}")
            return retry_count + 1

        await self.fail(message)
        return -1

    async def fail(self, message: str):
        self.task_status = "error"
        self.status = "error"
        await self.save_report(f"Image failed after retries, {message}", emit=False)
        await self.save_and_emit()
