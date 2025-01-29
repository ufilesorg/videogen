import json
import logging
import uuid
from io import BytesIO

import fal_client
import httpx
import ufiles
from apps.video.models import Video
from apps.video.schemas import (
    VideoResponse,
    VideoStatus,
    VideoWebhookData,
    VideoWebhookPayload,
)
from fastapi_mongo_base.tasks import TaskStatusEnum
from server.config import Settings
from utils import ai, finance


async def process_result(video: Video, file_res: str):
    ufiles_app = Settings.UFILES_BASE_URL.rstrip("/f")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ufiles_app}/apps/ffmpeg/details",
            headers={"x-api-key": Settings.UFILES_API_KEY},
            json={"url": file_res},
            timeout=None,
        )
        if response.status_code != 200:
            data = {"url": file_res, "duration": 5, "width": 512, "height": 512}
        else:
            data = response.json()
    video.results = VideoResponse(**data)
    await video.save()


async def upload_ufile(
    file_bytes: BytesIO,
    user_id: uuid.UUID,
    meta_data: dict | None = None,
    file_upload_dir: str = "videogens",
):
    client = ufiles.AsyncUFiles(
        ufiles_base_url=Settings.UFILES_BASE_URL,
        usso_base_url=Settings.USSO_BASE_URL,
        api_key=Settings.UFILES_API_KEY,
    )

    return await client.upload_bytes(
        file_bytes,
        filename=f"{file_upload_dir}/{file_bytes.name}",
        public_permission=json.dumps({"permission": ufiles.PermissionEnum.READ}),
        user_id=str(user_id),
        meta_data=meta_data,
        timeout=None,
    )


async def create_prompt(video: Video, enhance: bool = False):
    # Translate prompt using ai
    prompt = await ai.translate(video.prompt)
    prompt = prompt.strip(",").strip()
    return prompt


async def video_request(video: Video):
    try:
        usage = await finance.meter_cost(video)
        if usage is None:
            logging.error(f"Insufficient balance. {video.user_id} {video.engine.value}")
            await video.fail("Insufficient balance.")
            return

        prompt = await create_prompt(video)
        video.prompt = prompt
        data = {
            "prompt": video.prompt,
            "image_url": video.image_url,
            **(video.meta_data or {}),
        }
        handler = await fal_client.submit_async(
            video.engine.application_name,
            webhook_url=video.item_webhook_url,
            arguments=data,
        )
        video.request_id = handler.request_id
        video.task_status = TaskStatusEnum.processing
        video.status = VideoStatus.processing
        await video.save_report(f"{video.engine} has been requested.")
    except Exception as e:
        import traceback

        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        logging.error(f"Error updating imagination status: \n{traceback_str}\n{e}")

        video.status = VideoStatus.error
        video.task_status = VideoStatus.error.task_status
        await video.fail(f"{type(e)}: {e}")
        return video


async def get_fal_status(video: Video):
    # Get and convert fal status to VideoStatus
    status = await fal_client.status_async(
        video.engine.application_name, video.request_id, with_logs=True
    )
    video.status = VideoStatus.from_fal_status(type(status))

    # Check video status
    if video.status.is_done:
        payload: VideoWebhookPayload | None = None
        # Getting the video payload if the status was successful
        if video.status.is_success:
            results = await fal_client.result_async(
                video.engine.application_name, video.request_id
            )
            payload = VideoWebhookPayload(video=results["video"])
        # Delivery of the results to the web process
        await process_video_webhook(
            video, VideoWebhookData(status=video.status, payload=payload)
        )
    await video.save()


async def process_video_webhook(video: Video, data: VideoWebhookData):
    if data.status == VideoStatus.error:
        await video.retry(data.error)
        return

    if data.status.is_success:
        result_url = data.payload.video.get("url", "")
        async with httpx.AsyncClient() as session:
            try:
                response = await session.get(result_url, timeout=None)
                if response.status_code == 200:
                    video_bytes = BytesIO(response.content)
                    video_bytes.seek(0)
                    video_bytes.name = f"video{str(uuid.uuid4())}.mp4"
                    file = await upload_ufile(
                        video_bytes,
                        user_id=str(video.user_id),
                        file_upload_dir="videogens",
                    )
                    await process_result(video, file.url)
                else:
                    await process_result(video, result_url)
            except Exception as e:
                logging.error(f"Error processing video webhook {type(e)} {e}")
                await process_result(video, result_url)
        video.task_progress = 100
        video.status = VideoStatus.completed
        video.task_status = TaskStatusEnum.completed

        report = (
            f"Fal completed."
            if data.status == "completed"
            else f"Fal update. {video.status}"
        )

        await video.save_report(report)

    logging.warning(f"Video webhook {video.uid} {data.status}")
