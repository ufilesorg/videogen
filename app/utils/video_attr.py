import logging

import httpx
from server.config import Settings


async def get_attributes(file_res: str):
    ufiles_app = Settings.UFILES_BASE_URL.rstrip("/f")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ufiles_app}/apps/ffmpeg/details",
            headers={"x-api-key": Settings.UFILES_API_KEY},
            json={"url": file_res},
            timeout=None,
        )
        if response.status_code != 200:
            logging.error(
                f"get_attributes failed {response.text=}, {response.status_code=}"
            )
            data = {"url": file_res, "duration": 5, "width": 512, "height": 512}
        else:
            data = response.json()
    return data
