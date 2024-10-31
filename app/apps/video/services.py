import json
import logging
import re
import uuid
import boto3
import httpx
import aiohttp

from datetime import datetime
from httpx_socks import AsyncProxyTransport
from apps.video.models import Video
from apps.video.schemas import (
    VideoEngines,
    VideoStatus,
    VideoResponse,
    VideoStatusData,
)
from fastapi_mongo_base._utils.basic import try_except_wrapper
from PIL import Image
from fastapi import UploadFile
from botocore.client import Config
from server.config import Settings

def get_client():
    proxy_url = "socks5://127.0.0.1:1024"
    transport = AsyncProxyTransport.from_url(proxy_url)
    return httpx.AsyncClient(transport=transport)

async def process_result(video: Video):
    url = video.engine.get_request_url(video.request_id)
    headers = {
        "Authorization": f"Key {Settings.fal_key}",
    }

    async with get_client() as client:
        response = await client.get(url, headers=headers)
        try:
            file_res = response.json()['video']['url']
            video.results = VideoResponse(
                url=file_res,
                width=22,
                height=22,
                duration=3,
            )
            await video.save()
        except ValueError:
            print("Error text:", response.text)
    

async def get_fal_status(video: Video):
    url = f"{video.engine.get_request_url(video.request_id)}/status"
    headers = {
        "Authorization": f"Key {Settings.fal_key}",
    }

    async with get_client() as client:
        response = await client.get(url, headers=headers)
        try:
            result = response.json()
            return VideoStatus.from_fal(result.get("status"))
        except ValueError:
            return VideoStatus.in_queue
    
    
async def upload_image(image: UploadFile):
    s3 = boto3.client(
        "s3",
        endpoint_url=Settings.aws_endpoint_url,
        aws_access_key_id=Settings.aws_access_key,
        aws_secret_access_key=Settings.aws_secret_key,
        config=Config(signature_version="s3v4"),
    )
    filename = datetime.now().strftime("%Y%m%d%H%M%S") + image.filename
    s3.upload_fileobj(image.file, Settings.aws_bucket_name, filename, ExtraArgs={'ACL': 'public-read'} )
    
    return f"{Settings.aws_endpoint_url}/{Settings.aws_bucket_name}/{filename}"
    

@try_except_wrapper
async def video_request(video: Video):
    url = video.engine.get_fal_url
    headers = {
        "Authorization": f"Key {Settings.fal_key}",
        "Content-Type": "application/json"
    }
    data = {
        "prompt": video.prompt,
        "image_url": video.image,
        "prompt_optimizer": "True",
        "ratio": "16:9",
        "duration": "5",
    }
    async with get_client() as client:
        response = await client.post(url, headers=headers, json=data)
        video.request_id = response.json().get("request_id")
        await video.save_report(f"Engine has been requested.")
