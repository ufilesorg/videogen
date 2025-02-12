import logging
import uuid
from datetime import datetime
from apps.video.models import Video
from apps.video.schemas import (
    VideoCreateSchema,
    VideoEnginesSchema,
    VideoSchema,
    VideoWebhookData,
    VideoStatus,
)
from apps.video.services import process_video_webhook, register_cost
from fastapi import BackgroundTasks, Request, Query
from fastapi_mongo_base.routes import AbstractTaskRouter
from usso.fastapi import jwt_access_security
from utils import finance
from server.config import Settings


class VideoRouter(AbstractTaskRouter[Video, VideoSchema]):
    def __init__(self):
        super().__init__(
            model=Video,
            user_dependency=jwt_access_security,
            schema=VideoSchema,
            tags=["Video"],
            # prefix="",
        )

    def config_routes(self, **kwargs):
        super().config_routes(update_routes=False, **kwargs)
        self.router.add_api_route(
            "/{uid:uuid}/webhook",
            self.webhook,
            methods=["POST"],
            status_code=200,
        )

    async def statistics(
        self,
        request: Request,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        status: VideoStatus | None = None,
    ):
        return await super().statistics(request)

    async def create_item(
        self,
        request: Request,
        data: VideoCreateSchema,
        background_tasks: BackgroundTasks,
    ):
        item: Video = await super(AbstractTaskRouter, self).create_item(request, data)
        await finance.check_quota(item.user_id, item.engine_instance.price)
        await register_cost(item)
        item.status = VideoStatus.init
        item.task_status = "init"
        await item.save()
        background_tasks.add_task(item.start_processing)
        return item

    async def webhook(self, request: Request, uid: uuid.UUID, data: VideoWebhookData):
        logging.info(f"Webhook for video {uid}, {data=}")
        item: Video = await self.get_item(uid, user_id=None)
        if item.status == "cancelled":
            return {"message": "Video has been cancelled."}
        await process_video_webhook(item, data)
        return {}


router = VideoRouter().router


@router.get("/engines")
async def engines(text_to_video: bool | None = None, image_to_video: bool | None = None):
    from . import engines

    engines = [
        VideoEnginesSchema.from_model(name)
        for name, engine in engines.AbstractEngine.get_subclasses().items()
        if "abstract" not in engine.get_class_name()
        and (text_to_video is None or text_to_video == engine.text_to_video)
        and (image_to_video is None or image_to_video == engine.image_to_video)
    ]
    return engines
