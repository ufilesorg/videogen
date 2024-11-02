import uuid
import fastapi

from fastapi_mongo_base.routes import AbstractBaseRouter

from apps.video.models import Video
from apps.video.schemas import (
    VideoCreateSchema,
    VideoStatusData,
    VideoSchema,
    VideoEngines
)
from apps.video.services import get_fal_status, process_result, upload_image


class VideoRouter(AbstractBaseRouter[Video, VideoSchema]):
    def __init__(self):
        super().__init__(
            model=Video,
            user_dependency=None,
            schema=VideoSchema,
            tags=["Video"],
            prefix="",
        )

    def config_routes(self, **kwargs):
        self.router.add_api_route(
            "/create-item",
            self.create_item,
            methods=["POST"],
            response_model=self.create_response_schema,
            status_code=201,
        )
        self.router.add_api_route(
            "/{uid:uuid}/status",
            self.get_status,
            methods=["POST"],
            status_code=200,
        )
        self.router.add_api_route(
            "/upload-image",
            self.upload_image,
            methods=["POST"],
            status_code=200,
        )

    async def create_item(
        self, request: fastapi.Request, data: VideoCreateSchema
    ):
        item: Video = await super().create_item(request, data.model_dump())
        await item.start_processing()
        return item


    async def upload_image(
        self, request: fastapi.Request, file: fastapi.UploadFile=fastapi.File(...)
    ):
        return {'url': await upload_image(file)}

    async def get_status(
        self, request: fastapi.Request, uid: uuid.UUID
    ):
        item: Video = await self.get_item(uid, user_id=None)
        item.status = await get_fal_status(item)
        if item.status.is_done:
            await process_result(item)
        await item.save()
        return item
    
router = VideoRouter().router
