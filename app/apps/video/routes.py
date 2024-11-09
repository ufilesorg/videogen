import uuid
import fastapi

from typing import Any
from fastapi import BackgroundTasks, Request, UploadFile, File
from usso.fastapi import jwt_access_security
from fastapi_mongo_base.routes import AbstractBaseRouter

from apps.video.models import Video
from apps.video.services import upload_image, process_video_webhook
from apps.video.schemas import (
    VideoSchema,
    VideoEngines,
    VideoWebhookData,
    VideoCreateSchema,
    VideoEnginesSchema,
)

class VideoRouter(AbstractBaseRouter[Video, VideoSchema]):
    def __init__(self):
        super().__init__(
            model=Video,
            user_dependency=jwt_access_security,
            schema=VideoSchema,
            tags=["Video"],
            prefix="",
        )

    def config_routes(self, **kwargs):
        self.router.add_api_route(
            "",
            self.list_items,
            methods=["GET"],
            response_model=self.list_response_schema,
            status_code=200,
        )
        self.router.add_api_route(
            "/",
            self.create_item,
            methods=["POST"],
            response_model=self.create_response_schema,
            status_code=201,
        )
        self.router.add_api_route(
            "/{uid:uuid}",
            self.retrieve_item,
            methods=["GET"],
            response_model=self.retrieve_response_schema,
            status_code=200,
        )
        self.router.add_api_route(
            "/{uid:uuid}",
            self.delete_item,
            methods=["DELETE"],
            response_model=self.delete_response_schema,
        )
        self.router.add_api_route(
            "/upload-image",
            self.upload_image,
            methods=["POST"],
            status_code=200,
        )
        self.router.add_api_route(
            "/{uid:uuid}/webhook",
            self.webhook,
            methods=["POST"],
            status_code=200,
        )

    async def create_item(
        self, request: Request, data: VideoCreateSchema,
        background_tasks: BackgroundTasks,
    ):
        item: Video = await super().create_item(request, data.model_dump())
        background_tasks.add_task(item.start_processing)
        return item


    async def upload_image(
        self, request: Request, file: UploadFile=File(...)
    ):
        user_id = await self.get_user_id(request)
        return {'url': await upload_image(file, user_id=user_id)}
    
    async def webhook(
        self, request: Request, uid: uuid.UUID, data: VideoWebhookData
    ):
        item: Video = await self.get_item(uid, user_id=None)
        if item.status == "cancelled":  
            return {"message": "Video has been cancelled."}
        await process_video_webhook(item, data)
        return {}

router = VideoRouter().router


@router.get("/engines")
async def engines():
    engines = [VideoEnginesSchema.from_model(engine) for engine in VideoEngines]
    return engines
