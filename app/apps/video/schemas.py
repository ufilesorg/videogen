import fal_client

from enum import Enum
from typing import Any
from abc import ABC, abstractmethod
from pydantic import BaseModel, field_validator, model_validator
from fastapi_mongo_base.schemas import OwnedEntitySchema
from fastapi_mongo_base.tasks import TaskMixin, TaskStatusEnum

from utils import ufiles, imagetools

class Engines(ABC):
    application_name: str 
    thumbnail_url: str 
    
    def __init__(self, meta_data):
        self.meta_data = meta_data

    @property
    @abstractmethod
    def price(self):
        pass
    
    @abstractmethod
    def validate(self):
        pass
    
class RunwayEngine(Engines):
    application_name = "fal-ai/runway-gen3/turbo/image-to-video"
    thumbnail_url = "https://runwayml.com/icon.png"
    
    @property
    def price(self):
        duration = self.meta_data.get('duration', 5)
        return 0.25 if duration == 5 else 0.5

    def validate(self):
        duration = self.meta_data.get('duration', 5)
        ratio = self.meta_data.get('ratio', '16:9')
        duration_valid = duration in {5, 10}
        ratio_valid = ratio in {'16:9', '9:16'}
        if not duration_valid:
            message = "Duration must be 5 or 10"
        elif not ratio_valid:
            message = "Ratio must be 16:9 or 9:16"
        else:
            message = None
        return duration_valid and ratio_valid, message
    
class HailuoEngine(Engines):
    application_name = "fal-ai/minimax-video/image-to-video"
    thumbnail_url = "https://hailuoai.video/assets/img/side-nav-logo.png"
    
    @property
    def price(self):
        return 0.5

    def validate(self):
        prompt_optimizer = self.meta_data.get('prompt_optimizer', True)
        prompt_optimizer_valid = isinstance(prompt_optimizer, bool)
        if not prompt_optimizer_valid:
            message = "prompt_optimizer must be boolean"
        else:
            message = None
        return prompt_optimizer_valid, message
       
class KlingVideoEngine(Engines):
    application_name = "fal-ai/kling-video/v1/standard/image-to-video"
    thumbnail_url = "https://www.klingvideo.ai/assets/imgs/kling/klingvedioai-logo.png"
    
    @property
    def price(self):
        return 0.03 * self.meta_data.get('duration', 5)

    def validate(self):
        duration = self.meta_data.get('duration', 5)
        aspect_ratio = self.meta_data.get('aspect_ratio', '16:9')
        duration_valid = duration in {5, 10}
        aspect_ratio_valid = aspect_ratio in {'16:9', '9:16', '1:1'}
        if not duration_valid:
            message = "Duration must be 5 or 10"
        elif not aspect_ratio_valid:
            message = "aspect_ratio must be 16:9 or 9:16 or 1:1"
        else:
            message = None
        return duration_valid and aspect_ratio_valid, message
    
class KlingVideoProEngine(Engines):
    application_name = "fal-ai/kling-video/v1/pro/image-to-video"
    thumbnail_url = "https://www.klingvideo.ai/assets/imgs/kling/klingvedioai-logo.png"
    
    @property
    def price(self):
        return 0.125 * self.meta_data.get('duration', 5)

    def validate(self):
        duration = self.meta_data.get('duration', 5)
        aspect_ratio = self.meta_data.get('aspect_ratio', '16:9')
        duration_valid = duration in {5, 10}
        aspect_ratio_valid = aspect_ratio in {'16:9', '9:16', '1:1'}
        if not duration_valid:
            message = "Duration must be 5 or 10"
        elif not aspect_ratio_valid:
            message = "aspect_ratio must be 16:9 or 9:16 or 1:1"
        else:
            message = None
        return duration_valid and aspect_ratio_valid, message
    
class VideoEngines(str, Enum):
    runway = "runway"
    hailuo = "hailuo"
    kling_video = 'kling-video'
    kling_video_pro = 'kling-video-pro'
    
    def instance(self, meta_data):
        return ({
            VideoEngines.runway: RunwayEngine,
            VideoEngines.hailuo: HailuoEngine,
            VideoEngines.kling_video: KlingVideoEngine,
            VideoEngines.kling_video_pro: KlingVideoProEngine,
        }[self])(meta_data)

    @property
    def price(self, meta_data):
        return self.instance(meta_data).price

    @property
    def application_name(self):
        return self.instance({}).application_name

    @property
    def thumbnail_url(self):
        return self.instance({}).thumbnail_url

    def validate(self, meta_data):
        return self.instance(meta_data).validate()
    
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
    error = "ERROR"
    errorr = "error"
    ok = "OK"
    cancelled = "cancelled"

    @classmethod
    def from_fal(cls, status):
        return {
            "initialized": VideoStatus.init,
            "queue": VideoStatus.queue,
            "waiting": VideoStatus.waiting,
            "running": VideoStatus.processing,
            "completed": VideoStatus.completed,
            "ERROR": VideoStatus.error,
            "error": VideoStatus.error,
        }.get(status, VideoStatus.error)  

    @classmethod
    def from_fal_status(cls, status):
        return {
            fal_client.Queued: VideoStatus.queue,
            fal_client.InProgress: VideoStatus.processing,
            fal_client.Completed: VideoStatus.completed,
        }.get(status, VideoStatus.error)
        
    @property
    def done_statuses(self):
        return [
            VideoStatus.done,
            VideoStatus.completed,
            VideoStatus.ok,
            VideoStatus.cancelled,
            VideoStatus.error,
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
        return self in self.done_statuses

class VideoEnginesSchema(BaseModel):
    engine: VideoEngines = VideoEngines.runway
    thumbnail_url: str
    price: float

    @classmethod
    def from_model(cls, model: VideoEngines):
        return cls(engine=model, thumbnail_url=model.thumbnail_url, price=model.price)

class VideoCreateSchema(BaseModel):
    prompt: str
    image_url: str
    meta_data: dict[str, Any] | None = None
    engine: VideoEngines
    webhook_url: str | None = None
    
    @model_validator(mode='after')
    def validate_engine(cls, values):
        meta_data = values.meta_data or {}
        engine = values.engine
        validated, message = engine.validate(meta_data)
        if not validated:
            raise ValueError(f'MetaData: {message}')
        return values
    
class VideoResponse(BaseModel):
    url: str
    width: int
    height: int
    duration: int

class VideoSchema(TaskMixin, OwnedEntitySchema):
    prompt: str = None
    webhook_url: str | None = None
    request_id: str | None = None
    image_url: str | None = None
    engine: VideoEngines
    meta_data: dict[str, Any] | None = None
    status: VideoStatus = VideoStatus.draft
    results: VideoResponse | None = None

class VideoWebhookPayload(BaseModel):
    video: dict | None = None
    
class VideoWebhookData(BaseModel):
    payload: VideoWebhookPayload | None = None
    status: VideoStatus
    error: Any | None = None
    