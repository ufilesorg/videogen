import logging
import uuid
from io import BytesIO

import fal_client
import httpx
from apps.video.models import Video
from apps.video.schemas import (
    VideoResponse,
    VideoStatus,
    VideoWebhookData,
    VideoWebhookPayload,
)
from fastapi_mongo_base.tasks import TaskStatusEnum
from utils import ai, finance, media, video_attr


async def process_result(video: Video, file_res: str):
    data = await video_attr.get_attributes(file_res)
    video.results = VideoResponse(**data)
    await video.save()


async def create_prompt(video: Video, enhance: bool = False):
    # Translate prompt using ai
    prompt = await ai.translate(video.prompt)
    prompt = prompt.strip(",").strip()
    return prompt


async def video_request(video: Video):
    try:
        usage = await finance.meter_cost(video.user_id, video.engine.price)
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
                    file = await media.upload_ufile(
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
