import fal_client
from enum import Enum
from typing import Any, Literal
from fastapi import UploadFile, File

from fastapi_mongo_base.schemas import OwnedEntitySchema
from fastapi_mongo_base.tasks import TaskMixin, TaskStatusEnum
from pydantic import BaseModel, field_validator, model_validator
from utils import ufiles, imagetools
from abc import ABC, abstractmethod

class Engines(ABC):
    application_name: str 
    
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
    
class FluxEngine(Engines):
    application_name = "fal-ai/flux/schnell"
    
    @property
    def price(self):
        return 0.22

    def validate(self):
        return True, None
    
class VideoEngines(str, Enum):
    runway = "runway"
    hailuo = "hailuo"
    kling_video = 'kling-video'
    kling_video_pro = 'kling-video-pro'
    flux = "flux"
    
    def instance(self, meta_data):
        return ({
            VideoEngines.runway: RunwayEngine,
            VideoEngines.hailuo: HailuoEngine,
            VideoEngines.kling_video: KlingVideoEngine,
            VideoEngines.flux: FluxEngine,
            VideoEngines.kling_video_pro: KlingVideoProEngine,
        }[self])(meta_data)

    @property
    def price(self, meta_data):
        return self.instance(meta_data).price

    @property
    def application_name(self):
        return self.instance({}).application_name

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
    error = "error"
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
            "error": VideoStatus.error,
        }.get(status, VideoStatus.error)  

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
    def is_done(self):
        return self in (
            VideoStatus.done,
            VideoStatus.completed,
            VideoStatus.ok,
        )


class VideoCreateSchema(BaseModel):
    prompt: str | None = None
    image_url: str = ''
    meta_data: dict[str, Any] | None = None
    engine: VideoEngines
    
    # Validator for 'engine' field
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
    prompt: str | None = None
    image_url: str | None = None
    engine: VideoEngines
    status: VideoStatus = VideoStatus.draft
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


class VideoWebhookPayload(BaseModel):
    video: dict | None = None
    
class VideoWebhookData(BaseModel):
    request_id: str
    gateway_request_id: str
    payload: VideoWebhookPayload
    status: VideoStatus
    error: Any | None = None
    