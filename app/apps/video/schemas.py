import uuid
from enum import Enum
from typing import Any

import fal_client
from fastapi_mongo_base.schemas import OwnedEntitySchema
from fastapi_mongo_base.tasks import TaskMixin, TaskStatusEnum
from pydantic import BaseModel, field_validator, model_validator

from . import engines


class VideoStatus(str, Enum):
    none = "none"
    draft = "draft"
    init = "init"
    queue = "queue"
    waiting = "waiting"
    running = "running"
    processing = "processing"
    done = "done"
    completed = "completed"
    error = "error"
    cancelled = "cancelled"

    @classmethod
    def from_engine(cls, status):
        return {
            "initialized": VideoStatus.init,
            "queue": VideoStatus.queue,
            "waiting": VideoStatus.waiting,
            "running": VideoStatus.processing,
            "completed": VideoStatus.completed,
            "ERROR": VideoStatus.error,
            "error": VideoStatus.error,
            "queued": VideoStatus.queue,
            "inprogress": VideoStatus.processing,
            "completed": VideoStatus.completed,
            "SUCCEEDED": VideoStatus.completed,
            "FAILED": VideoStatus.error,
            "RUNNING": VideoStatus.processing,
            "PENDING": VideoStatus.queue,
            "CANCELLED": VideoStatus.cancelled,
            "THROTTLED": VideoStatus.error,
        }.get(status, VideoStatus.error)

    @classmethod
    def from_fal_status(cls, status):
        return {
            fal_client.Queued: VideoStatus.queue,
            fal_client.InProgress: VideoStatus.processing,
            fal_client.Completed: VideoStatus.completed,
        }.get(status, VideoStatus.error)

    @classmethod
    def from_runway(cls, status: str):
        return {
            "SUCCEEDED": VideoStatus.completed,
            "FAILED": VideoStatus.error,
        }.get(status, VideoStatus.error)

    @classmethod
    def done_statuses(cls):
        return [
            status.value
            for status in [
                VideoStatus.done,
                VideoStatus.completed,
                VideoStatus.ok,
                VideoStatus.cancelled,
                VideoStatus.error,
            ]
        ]

    @property
    def task_status(self):
        return {
            VideoStatus.none: TaskStatusEnum.none,
            VideoStatus.draft: TaskStatusEnum.draft,
            VideoStatus.init: TaskStatusEnum.init,
            VideoStatus.queue: TaskStatusEnum.processing,
            VideoStatus.waiting: TaskStatusEnum.processing,
            VideoStatus.running: TaskStatusEnum.processing,
            VideoStatus.processing: TaskStatusEnum.processing,
            VideoStatus.done: TaskStatusEnum.completed,
            VideoStatus.completed: TaskStatusEnum.completed,
            VideoStatus.ok: TaskStatusEnum.completed,
            VideoStatus.error: TaskStatusEnum.error,
            VideoStatus.cancelled: TaskStatusEnum.completed,
        }[self]

    @property
    def is_success(self):
        return self in (
            VideoStatus.done,
            VideoStatus.completed,
            VideoStatus.ok,
        )

    @property
    def is_done(self):
        return self in self.done_statuses()


class VideoEnginesSchema(BaseModel):
    engine: str = "runway"
    text_to_video: bool = True
    image_to_video: bool = False
    thumbnail_url: str
    price: float

    @classmethod
    def from_model(cls, model: str) -> "VideoEnginesSchema":
        subclass = engines.AbstractEngine.get_subclass(model)
        return cls(
            engine=subclass.get_class_name(),
            thumbnail_url=subclass.thumbnail_url,
            price=subclass.price,
            text_to_video=subclass.text_to_video,
            image_to_video=subclass.image_to_video,
        )


class VideoCreateSchema(BaseModel):
    # prompt: str
    user_prompt: str | None = None
    image_url: str | None = None
    meta_data: dict[str, Any] | None = None
    engine: str = "runway"
    webhook_url: str | None = None

    @field_validator("engine", mode="before")
    def validate_engine(cls, v: str):
        engines.AbstractEngine.get_subclass(v)
        return v

    @field_validator("user_prompt", mode="before")
    def validate_user_prompt(cls, v: str):
        if v is None:
            raise ValueError("User prompt is required")
        return v

    @property
    def engine_instance(self):
        return engines.AbstractEngine.get_subclass(self.engine)

    @model_validator(mode="after")
    def validate_metadata(cls, values: "VideoCreateSchema"):
        meta_data = values.meta_data or {}
        engine = engines.AbstractEngine.get_subclass(values.engine)
        validated, message = engine.validate(meta_data)
        if not validated:
            raise ValueError(f"MetaData: {message}")
        return values


class VideoResponse(BaseModel):
    url: str
    width: int
    height: int
    duration: float


class VideoSchema(VideoCreateSchema, TaskMixin, OwnedEntitySchema):
    prompt: str | None = None
    request_id: str | None = None
    status: VideoStatus = VideoStatus.draft
    results: VideoResponse | None = None
    usage_id: uuid.UUID | None = None

    @field_validator("user_prompt", mode="before")
    def validate_user_prompt(cls, v: str):
        if v is None:
            return None
        return v

    @field_validator("engine", mode="before")
    def validate_engine(cls, v: str):
        return v


class VideoWebhookPayload(BaseModel):
    video: dict | None = None


class VideoWebhookData(BaseModel):
    payload: VideoWebhookPayload | None = None
    status: VideoStatus
    error: Any | None = None
