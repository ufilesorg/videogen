import os

from fastapi_mongo_base.utils import basic
from pydantic import BaseModel
from singleton import Singleton


class VideoTaskSchema(BaseModel):
    url: str
    error: str | None = None
    status: str


class AbstractEngine(metaclass=Singleton):
    application_name: str
    thumbnail_url: str
    text_to_video: bool = False
    image_to_video: bool = False

    @classmethod
    def get_class_name(cls) -> str:
        return cls.__name__.lower().replace("engine", "").replace("video", "")

    @classmethod
    def get_subclasses(cls) -> dict[str, "AbstractEngine"]:
        return {
            subclass.__name__.lower()
            .replace("engine", "")
            .replace("video", ""): subclass()
            for subclass in basic.get_all_subclasses(cls)
        }

    @classmethod
    def get_subclass(cls, name: str) -> "AbstractEngine":
        subclasses = cls.get_subclasses()
        if name.lower().replace("engine", "").replace("video", "") not in subclasses:
            import logging
            logging.error(f"Subclass with application name {name} not found")
            return None
            # raise ValueError(f"Subclass with application name {name} not found")
        return subclasses.get(name.lower().replace("engine", "").replace("video", ""))

    @property
    def price(self):
        raise NotImplementedError("This method should be implemented by the subclass")

    def validate(self, meta_data: dict) -> tuple[bool, str]:
        raise NotImplementedError("This method should be implemented by the subclass")

    async def generate_async(
        self,
        prompt: str,
        *,
        image_url: str = None,
        meta_data: dict = None,
        webhook_url: str = None,
        **kwargs,
    ) -> str:
        raise NotImplementedError("This method should be implemented by the subclass")

    async def get_status(self, request_id: str) -> str:
        raise NotImplementedError("This method should be implemented by the subclass")

    async def get_result(self, request_id: str) -> VideoTaskSchema:
        raise NotImplementedError("This method should be implemented by the subclass")


class AbstractImageToVideoEngine(AbstractEngine):
    application_name: str
    thumbnail_url: str
    text_to_video: bool = False
    image_to_video: bool = True


class AbstractTextToVideoEngine(AbstractEngine):
    application_name: str
    thumbnail_url: str
    text_to_video: bool = True
    image_to_video: bool = False


class AbstractFalEngine(AbstractEngine):
    @property
    def price(self):
        return 75

    async def generate_async(
        self,
        prompt: str,
        *,
        image_url: str = None,
        meta_data: dict = None,
        webhook_url: str = None,
        **kwargs,
    ):
        import fal_client

        meta_data = meta_data or {}
        self.validate(meta_data)

        data = (
            {
                "prompt": prompt,
                **meta_data,
            }
            | {"image_url": image_url}
            if image_url
            else {}
        )
        handler = await fal_client.submit_async(
            self.application_name,
            webhook_url=webhook_url,
            arguments=data,
        )
        return handler.request_id

    async def get_status(self, request_id: str):
        import fal_client

        status = await fal_client.status_async(
            self.application_name, request_id, with_logs=True
        )
        return status.__class__.__name__.lower()

    async def get_result(self, request_id: str):
        import fal_client

        result = await fal_client.result_async(self.application_name, request_id)

        url = result.get("video", {}).get("url")
        error = result.get("error")
        status = result.get("status")
        return VideoTaskSchema(url=url, error=error, status=status)


class AbstractMinimaxEngine(AbstractFalEngine):
    thumbnail_url = "https://media.pixiee.io/v1/f/8f1e0257-e2ad-454d-b81c-9d09a6aa7916/hailuo-icon.png"

    @property
    def price(self):
        return 150

    def validate(self, meta_data: dict):
        prompt_optimizer = meta_data.get("prompt_optimizer", True)
        prompt_optimizer_valid = isinstance(prompt_optimizer, bool)
        if not prompt_optimizer_valid:
            message = "prompt_optimizer must be boolean"
        else:
            message = None
        return prompt_optimizer_valid, message


class HailouEngine(AbstractMinimaxEngine, AbstractImageToVideoEngine):
    application_name = "fal-ai/minimax/video-01/image-to-video"
    # application_name = "fal-ai/minimax-video/image-to-video"


class HailouTextEngine(AbstractMinimaxEngine, AbstractTextToVideoEngine):
    application_name = "fal-ai/minimax/video-01"


class AbstractKlingEngine(AbstractFalEngine):
    thumbnail_url = "https://media.pixiee.io/v1/f/abe6c5ae-3d88-4d67-a5a8-d421042522a4/kling-video-icon.png"

    @property
    def price(self):
        return 45

    def validate(self, meta_data: dict):
        duration = meta_data.get("duration", 5)
        aspect_ratio = meta_data.get("aspect_ratio", "16:9")
        duration_valid = duration in {5, 10}
        aspect_ratio_valid = aspect_ratio in {"16:9", "9:16", "1:1"}
        if not duration_valid:
            message = "Duration must be 5 or 10"
        elif not aspect_ratio_valid:
            message = "aspect_ratio must be 16:9 or 9:16 or 1:1"
        else:
            message = None
        return duration_valid and aspect_ratio_valid, message


class KlingTextVideoEngine(AbstractKlingEngine, AbstractTextToVideoEngine):
    application_name = "fal-ai/kling-video/v1/standard/text-to-video"

    @property
    def price(self):
        return 45


class KlingVideoEngine(AbstractKlingEngine, AbstractImageToVideoEngine):
    application_name = "fal-ai/kling-video/v1/standard/image-to-video"

    @property
    def price(self):
        return 45


class KlingProTextVideoEngine(AbstractKlingEngine, AbstractTextToVideoEngine):
    application_name = "fal-ai/kling-video/v1.6/standard/text-to-video"

    @property
    def price(self):
        return 45


class KlingProVideoEngine(AbstractKlingEngine, AbstractTextToVideoEngine):
    application_name = "fal-ai/kling-video/v1.6/pro/image-to-video"

    @property
    def price(self):
        return 150


class HunyuanEngine(AbstractFalEngine, AbstractTextToVideoEngine):
    application_name = "fal-ai/hunyuan-video"
    thumbnail_url = "https://media.pixiee.io/v1/f/bdefc333-f9d6-4d48-9f88-62230baa72a6/runway-icon.png"

    def validate(self, meta_data: dict):
        duration = meta_data.get("duration", 5)
        duration_valid = duration in {5, 10}
        if not duration_valid:
            message = "Duration must be 5 or 10"
        else:
            message = None
        return duration_valid, message

    @property
    def price(self):
        return 120


class HunyuanImageToVideoEngine(AbstractFalEngine, AbstractImageToVideoEngine):
    application_name = "fal-ai/hunyuan-video-img2vid-lora"
    thumbnail_url = "https://media.pixiee.io/v1/f/bdefc333-f9d6-4d48-9f88-62230baa72a6/runway-icon.png"

    @property
    def price(self):
        return 90


class RunwayEngine(AbstractImageToVideoEngine):
    application_name = "runway-gen3"
    thumbnail_url = "https://media.pixiee.io/v1/f/bdefc333-f9d6-4d48-9f88-62230baa72a6/runway-icon.png"
    text_to_video: bool = False
    image_to_video: bool = True

    @property
    def price(self):
        return 75

    def validate(self, meta_data: dict):
        duration = meta_data.get("duration", 5)
        ratio = meta_data.get("ratio", "1280:768")
        duration_valid = duration in {5, 10}
        ratio_valid = ratio in {"1280:768", "768:1280"}
        if not duration_valid:
            message = "Duration must be 5 or 10"
        elif not ratio_valid:
            message = "Ratio must be 1280:768 or 768:1280"
        else:
            message = None
        return duration_valid and ratio_valid, message

    async def generate_async(
        self,
        prompt: str,
        *,
        image_url: str = None,
        meta_data: dict = None,
        webhook_url: str = None,
        **kwargs,
    ):
        from runwayml import AsyncRunwayML

        meta_data = meta_data or {}

        self.validate(meta_data)

        async with AsyncRunwayML(api_key=os.getenv("RUNWAY_API_KEY")) as runway:
            task = await runway.image_to_video.create(
                model="gen3a_turbo",
                prompt_text=prompt,
                prompt_image=image_url,
                duration=meta_data.get("duration", 5),
                ratio=meta_data.get("ratio", "1280:768"),
            )

        return task.id

    async def _get_task(self, request_id: str):
        from runwayml import AsyncRunwayML

        async with AsyncRunwayML(api_key=os.getenv("RUNWAY_API_KEY")) as runway:
            task = await runway.tasks.retrieve(request_id)
        return task

    async def get_status(self, request_id: str):
        task = await self._get_task(request_id)
        return task.status

    async def get_result(self, request_id: str):
        task = await self._get_task(request_id)
        if task.output:
            url = task.output[0]
        else:
            url = None
        return VideoTaskSchema(
            url=url, error=task.failure, status=task.status
        )
