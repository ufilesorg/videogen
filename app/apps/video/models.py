from fastapi_mongo_base.models import BaseEntity
from server.config import Settings

from .schemas import VideoSchema


class Video(VideoSchema, BaseEntity):
    class Settings:
        indexes = BaseEntity.Settings.indexes

    @property
    def item_url(self):
        return f"https://{Settings.root_url}/v1/apps/video/video/{self.uid}"

    async def start_processing(self):
        from apps.video.services import video_request

        await video_request(self)
