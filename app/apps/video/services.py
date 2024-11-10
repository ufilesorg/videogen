import re
import json
import uuid
import logging
import aiohttp
import requests
import fal_client

from io import BytesIO
from PIL import Image
from fastapi import UploadFile
from datetime import datetime, timedelta
from usso.async_session import AsyncUssoSession
from fastapi_mongo_base._utils.basic import try_except_wrapper

from apps.video.models import Video
from utils import ufiles, imagetools
from apps.video.schemas import (
    VideoStatus,
    VideoResponse,
    VideoWebhookData,
    VideoWebhookPayload
)

def sanitize_uploadfilename(image_name: str):
    return str(uuid.uuid4()) + image_name

def sanitize_filename(prompt: str):
    # Remove invalid characters and replace spaces with underscores
    # Valid characters: alphanumeric, underscores, and periods
    prompt_parts = prompt.split(",")
    prompt = prompt_parts[1] if len(prompt_parts) > 1 else prompt
    prompt = prompt.strip()
    position = prompt.find(" ", 80)
    if position > 120 or position == -1:
        position = 100
    sanitized = re.sub(r"[^a-zA-Z0-9_. ]", "", prompt)
    sanitized = sanitized.replace(" ", "_")  # Replace spaces with underscores
    return sanitized[:position]  # Limit to 100 characters

async def process_result(video: Video, file_res: str):
    video.results = VideoResponse(
        url=file_res,
        width=22,
        height=22,
        duration=5,
    )
    await video.save()

async def upload_ufile(
    file_bytes: BytesIO,
    user_id: uuid.UUID, 
    meta_data: dict | None = None,
    file_upload_dir: str = "imaginations",
):
    async with AsyncUssoSession(
        ufiles.AsyncUFiles().refresh_url,
        ufiles.AsyncUFiles().refresh_token,
    ) as client:
        return await ufiles.AsyncUFiles().upload_bytes_session(
            client,
            file_bytes,
            filename=f"{file_upload_dir}/{file_bytes.name}",
            public_permission=json.dumps({"permission": ufiles.PermissionEnum.READ}),
            user_id=str(user_id),
            meta_data=meta_data,
        )
    
async def upload_image(image: UploadFile, user_id):
    image_data = await image.read()
    image_stream = BytesIO(image_data)
    pil_image = Image.open(image_stream)
    image_name = sanitize_uploadfilename(image.filename)
    
    image_bytes = imagetools.convert_to_webp_bytes(pil_image)
    image_bytes.name = f"{image_name}.webp"
    uploaded_image = await upload_ufile(
        image_bytes,
        user_id=str(user_id),
        file_upload_dir='imaginations'
    )
    
    return uploaded_image.url

async def create_prompt(video: Video, enhance: bool = False):

    return video.prompt

@try_except_wrapper
async def video_request(video: Video):
    prompt = await create_prompt(video)
    video.prompt = prompt
    data = {
        "prompt": video.prompt,
        "image_url": video.image_url,
        **(video.meta_data or {})
    }
    handler = await fal_client.submit_async(
        video.engine.application_name,
        # webhook_url=video.service_webhook_url,
        arguments=data,
    )
    video.request_id = handler.request_id
    await video.save_report(f"{video.engine} has been requested.")

async def get_fal_status(video: Video):
    logging.info(f'Check Video status with uid: {video.uid}')
    # Get and convert fal status to VideoStatus
    status = await fal_client.status_async(video.engine.application_name, video.request_id, with_logs=True)
    video.status = VideoStatus.from_fal_status(type(status))
    # Check video status
    if video.status.is_done:
        payload: VideoWebhookPayload | None = None
        # Getting the video payload if the status was successful
        if video.status.is_success:
            results = await fal_client.result_async(video.engine.application_name, video.request_id)
            payload = VideoWebhookPayload(video=results['video'])
        # Delivery of the results to the web process
        await process_video_webhook(video, VideoWebhookData(status=video.status, payload=payload))
    await video.save()  

async def process_video_webhook(video: Video, data: VideoWebhookData):
    if data.status == VideoStatus.error:
        await video.retry(data.error)
        return

    if data.status.is_success:
        result_url = data.payload.video.get('url', '')
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(result_url) as response:
                    if response.status == 200:
                        video_bytes = BytesIO(await response.read())
                        video_bytes.seek(0)
                        video_bytes.name = f"video{str(uuid.uuid4())}.mp4"
                        file = await upload_ufile(
                            video_bytes,
                            user_id=str(video.user_id),
                            file_upload_dir='imaginations'
                        )
                        await process_result(video, file.url)
                    else:
                        await process_result(video, result_url)
            except Exception as e:
                print(e)
                await process_result(video, result_url)
    video.task_progress = 100
    video.status = VideoStatus.completed

    report = (
        f"Fal completed."
        if data.status == "completed"
        else f"Fal update. {video.status}"
    )

    if video.webhook_url:
        requests.post(video.webhook_url, data=video.json(), headers={'Content-Type': 'application/json'})

    await video.save_report(report)
