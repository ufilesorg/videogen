from io import BytesIO

import fal_client
from apps.video.models import Video
from apps.video.schemas import VideoResponse, VideoStatus
from fastapi import UploadFile
from fastapi_mongo_base._utils.basic import try_except_wrapper
from PIL import Image


async def process_result(video: Video):
    result = await fal_client.result_async(
        f"fal-ai{video.engine.get_bot_url}", video.request_id
    )
    file_res = result["video"]["url"]
    video.results = VideoResponse(
        url=file_res,
        width=22,
        height=22,
        duration=5,
    )
    await video.save()


async def get_fal_status(video: Video):
    status = await fal_client.status_async(
        f"fal-ai{video.engine.get_bot_url}", video.request_id, with_logs=True
    )
    return VideoStatus.from_fal(type(status))


async def upload_image(image: UploadFile):
    image_data = await image.read()
    image_stream = BytesIO(image_data)
    pil_image = Image.open(image_stream)
    return await fal_client.upload_image_async(image=pil_image, format=pil_image.format)


def on_queue_update(update):
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            print(log["message"])


@try_except_wrapper
async def video_request(video: Video):
    data = {
        "prompt": video.prompt,
        "image_url": video.image,
        "ratio": "16:9",
        "duration": "5",
    }
    handler = await fal_client.submit_async(
        f"fal-ai{video.engine.get_bot_url}",
        arguments=data,
    )
    video.request_id = handler.request_id
    await video.save_report(f"Engine has been requested.")
