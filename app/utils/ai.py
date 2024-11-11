import json
import logging
import os
from datetime import datetime
from typing import Literal

import aiohttp
import langdetect
import singleton
from metisai.async_metis import AsyncMetisBot
from pydantic import BaseModel, field_validator
from utils.texttools import backtick_formatter

metis_client = AsyncMetisBot(
    api_key=os.getenv("METIS_API_KEY"), bot_id=os.getenv("METIS_BOT_ID")
)


async def metis_chat(messages: dict, **kwargs):
    user_id = kwargs.get("user_id")
    session = await metis_client.create_session(user_id)
    prompt = "\n\n".join([message["content"] for message in messages])
    response = await metis_client.send_message(session, prompt)
    await metis_client.delete_session(session)
    resp_text = backtick_formatter(response.content)
    return resp_text


async def answer_messages(messages: dict, **kwargs):
    # resp_text = await openai_chat(messages, **kwargs)
    resp_text = await metis_chat(messages, **kwargs)
    try:
        return json.loads(resp_text)
    except json.JSONDecodeError:
        return {"answer": resp_text}


async def translate(query: str, to: str = "en"):
    try:
        lang = langdetect.detect(query)
    except:
        lang = "en"

    if lang == to:
        return query

    languages = {
        "en": "English",
        "fa": "Persian",
    }
    if not languages.get(to):
        to = "en"
    prompt = "\n".join(
        [
            f"You are perfect translator to {to} language.",
            f"Just reply the answer in json format like",
            f'`{{"answer": "Your translated text"}}`',
            f"",
            f"Translate the following text to '{to}': \"{query}\".",
        ]
    )

    messages = [{"content": prompt}]
    response = await answer_messages(messages)
    logging.info(f"process_task {query} {response}")
    return response["answer"]

    session = await metis_client.create_session()
    response = await metis_client.send_message(session, prompt)
    await metis_client.delete_session(session)
    resp_text = backtick_formatter(response.content)
    return resp_text


class MidjourneyDetails(BaseModel):
    deleted: bool = False
    active: bool = True
    createdBy: str | None = None
    user: str | None = None
    prompt: str
    command: str
    callback_url: str | None = None
    free: bool = False
    status: Literal[
        "initialized", "queue", "waiting", "running", "completed", "error"
    ] = "initialized"
    percentage: int = 0
    temp_uri: list[str] = []
    createdAt: datetime
    updatedAt: datetime
    uuid: str
    turn: int = 0
    account: str | None = None
    uri: str | None = None

    error: dict | str | None = None
    message: str | None = None
    result: dict | None = None
    sender_data: dict | None = None

    @field_validator("percentage", mode="before")
    def validate_percentage(cls, value):
        if value is None:
            return -1
        if isinstance(value, str):
            return int(value.replace("%", ""))
        if value < -1:
            return -1
        if value > 100:
            return 100
        return value


class Midjourney(metaclass=singleton.Singleton):
    def __init__(self) -> None:
        super().__init__()
        self.model_type = "image"
        self.api_url = "https://mid.aision.io/task"
        self.token = os.getenv("MIDAPI_TOKEN")

        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }

    def get_function(self, func_name: str):
        functions = {
            "imagine": self.imagine,
            # "upscale": self.upscale,
            # "variation": self.variate,
            # "zoomout": self.zoomout,
            # "blend": self.blend,
            # "redesign": self.redesign,
        }
        return functions.get(func_name)

    async def get_result(self, result_id: str, **kwargs) -> MidjourneyDetails:
        url = f"{self.api_url}/{result_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                result = await response.json()
        # if result.get("url"):
        #     result.update({"results": result.get("url")})
        return MidjourneyDetails(**result)

    async def _request(self, prompt, command, **kwargs) -> MidjourneyDetails:
        payload = json.dumps(
            {
                "prompt": prompt,
                "command": command,
                "callback": kwargs.get("callback", None),
            }
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=self.api_url, headers=self.headers, data=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return MidjourneyDetails(**result)

        # if command == "describe":
        #     image = AIModel.AIImage(**result)
        #     return image
        #     return result

    async def imagine(self, prompt: str, **kwargs):
        prompt = " ".join([im for im in kwargs.get("images", [])] + [prompt])
        response = await self._request(prompt, "imagine", **kwargs)
        return response
