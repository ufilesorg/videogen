import logging
from datetime import datetime
from apps.video.models import Video
from apps.video.schemas import (
    VideoResponse,
    VideoStatus,
    VideoWebhookData,
    VideoWebhookPayload,
)
from fastapi_mongo_base.tasks import TaskStatusEnum
from fastapi_mongo_base.utils import texttools
from utils import ai, finance, media, video_attr


async def get_attributes(file_url: str):
    data = await video_attr.get_attributes(file_url)
    url = data.pop("url", None) or file_url
    logging.info(f"get attributes {data}")
    return VideoResponse(**data, url=url)


async def create_prompt(user_prompt: str):
    # Translate prompt using ai
    prompt = await ai.translate(user_prompt)
    prompt = prompt.strip(",").strip()
    return prompt


async def video_request(video: Video):
    try:
        usage = await finance.meter_cost(video.user_id, video.engine_instance.price)
        if usage is None:
            logging.error(
                f"Insufficient balance. {video.user_id} {video.engine_instance.get_class_name()}"
            )
            await video.fail("Insufficient balance.")
            return

        video.task_start_time = datetime.now()
        prompt = await create_prompt(video.user_prompt)
        video.prompt = prompt
        engine = video.engine_instance
        video.request_id = await engine.generate_async(
            video.prompt,
            image_url=video.image_url,
            meta_data=video.meta_data,
            webhook_url=video.item_webhook_url,
        )
        video.task_status = TaskStatusEnum.processing
        video.status = VideoStatus.processing
        await video.save_report(
            f"{video.engine_instance.get_class_name()} has been requested."
        )
    except Exception as e:
        import traceback

        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        logging.error(f"Error updating imagination status: \n{traceback_str}\n{e}")

        video.status = VideoStatus.error
        video.task_status = VideoStatus.error.task_status
        await video.fail(f"{type(e)}: {e}")
        return video


async def get_update(video: Video):
    # Get and convert fal status to VideoStatus
    engine = video.engine_instance
    if engine is None:
        logging.error(f"Engine {video.engine} not found")
        return
    status = await engine.get_status(video.request_id)
    video.status = VideoStatus.from_engine(status)

    # Check video status
    if video.status.is_done:
        payload: VideoWebhookPayload | None = None
        # Getting the video payload if the status was successful
        if video.status.is_success:
            results = await engine.get_result(video.request_id)
            payload = VideoWebhookPayload(video=results.model_dump())
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
        filename = texttools.sanitize_filename(video.prompt)
        file = await media.upload_url(
            result_url,
            str(video.user_id),
            f"video-{filename}.mp4",
            file_upload_dir="videogens",
        )
        attributes = await get_attributes(file.url)
        video.results = attributes
        video.task_progress = 100
        video.status = VideoStatus.completed
        video.task_status = TaskStatusEnum.completed
        video.task_end_time = datetime.now()

        report = (
            f"Video task completed."
            if data.status == "completed"
            else f"Video task update. {video.status}"
        )

        await video.save_report(report)

    logging.info(f"Video webhook {video.uid} {data.status}")


async def register_cost(video: Video):
    usage = await finance.meter_cost(video.user_id, video.engine_instance.price)
    if usage is None:
        logging.error(
            f"Insufficient balance. {video.user_id} {video.engine_instance.get_class_name()}"
        )
        await video.fail("Insufficient balance.")
        return

    video.usage_id = usage.uid
    return video
