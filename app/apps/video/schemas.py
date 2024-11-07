from enum import Enum

import fal_client
from fastapi_mongo_base.schemas import BaseEntitySchema
from fastapi_mongo_base.tasks import TaskMixin
from pydantic import BaseModel, field_validator


class VideoStatus(str, Enum):
    in_queue = "IN_QUEUE"
    in_progress = "IN_PROGRESS"
    completed = "COMPLETED"
    error = "error"

    @classmethod
    def from_fal(cls, status):
        return {
            fal_client.Queued: VideoStatus.in_queue,
            fal_client.InProgress: VideoStatus.in_progress,
            fal_client.Completed: VideoStatus.completed,
        }.get(status, VideoStatus.error)

    @property
    def is_done(self):
        return self in (VideoStatus.completed,)


class VideoEngines(str, Enum):
    runway = "runway"
    minimax = "minimax"
    kling_video = "kling-video"
    kling_video_pro = "kling-video-pro"

    @property
    def get_bot_url(self):
        return {
            VideoEngines.runway: "/runway-gen3/turbo/image-to-video",
            VideoEngines.minimax: "/minimax-video/image-to-video",
            VideoEngines.kling_video: "/kling-video/v1/standard/image-to-video",
            VideoEngines.kling_video_pro: "/kling-video/v1/pro/image-to-video",
        }[self]

    @property
    def get_bot_value(self):
        return {
            VideoEngines.runway: "runway-gen3",
            VideoEngines.minimax: "minimax-video",
            VideoEngines.kling_video: "kling-video",
            VideoEngines.kling_video_pro: "kling-video",
        }[self]

    @property
    def thumbnail_url(self):
        return {
            VideoEngines.runway: "https://runwayml.com/icon.png",
            VideoEngines.minimax: "https://hailuoai.video/assets/img/side-nav-logo.png",
            VideoEngines.kling_video: "https://www.klingvideo.ai/assets/imgs/kling/klingvedioai-logo.png",
            VideoEngines.kling_video_pro: "https://www.klingvideo.ai/assets/imgs/kling/klingvedioai-logo.png",
        }.get(self, "")

    @property
    def get_fal_url(self):
        return f"https://queue.fal.run/fal-ai{self.get_bot_url}/"

    def get_request_url(self, request_id: str | int):
        return (
            f"https://queue.fal.run/fal-ai/{self.get_bot_value}/requests/{request_id}"
        )

    @property
    def price(self):
        return 0.25 if self.value == self.runway else 0.5


class VideoEnginesSchema(BaseModel):
    engine: VideoEngines = VideoEngines.runway
    thumbnail_url: str
    price: float

    @classmethod
    def from_model(cls, model: VideoEngines):
        return cls(engine=model, thumbnail_url=model.thumbnail_url, price=model.price)


class VideoCreateSchema(BaseModel):
    prompt: str
    image: str
    engine: VideoEngines = VideoEngines.runway


class VideoResponse(BaseModel):
    url: str
    width: int
    height: int
    duration: int


class VideoSchema(TaskMixin, BaseEntitySchema):
    prompt: str
    engine: VideoEngines = VideoEngines.runway
    status: VideoStatus = VideoStatus.in_queue
    image: str | None = ""
    request_id: str | int | None = None
    results: VideoResponse | None = None


class VideoStatusData(BaseModel):
    request_id: str | int
    percentage: int = 0

    @field_validator("percentage", mode="before")
    def validate_percentage(cls, value):
        if value is None:
            return -1
        if isinstance(value, str):
            return int(value.replace("%", ""))
        if value < -1:
            return -1
        if value > 100:
            return 100
        return value
