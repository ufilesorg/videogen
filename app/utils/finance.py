import uuid

from apps.video.models import Video
from fastapi_mongo_base.utils.basic import try_except_wrapper
from server.config import Settings
from ufaas import AsyncUFaaS, exceptions
from ufaas.apps.saas.schemas import UsageCreateSchema


async def meter_cost(video: Video):
    ufaas_client = AsyncUFaaS(
        ufaas_base_url=Settings.UFAAS_BASE_URL,
        usso_base_url=Settings.USSO_BASE_URL,
        # TODO: Change to UFAAS_API_KEY name
        api_key=Settings.UFILES_API_KEY,
    )
    usage_schema = UsageCreateSchema(
        user_id=video.user_id,
        asset="coin",
        amount=video.engine.price,
        variant="video",
    )
    usage = await ufaas_client.saas.usages.create_item(
        usage_schema.model_dump(mode="json"), timeout=30
    )
    video.usage_id = usage.uid
    await video.save()
    return usage


@try_except_wrapper
async def get_quota(user_id: uuid.UUID):
    ufaas_client = AsyncUFaaS(
        ufaas_base_url=Settings.UFAAS_BASE_URL,
        usso_base_url=Settings.USSO_BASE_URL,
        # TODO: Change to UFAAS_API_KEY name
        api_key=Settings.UFILES_API_KEY,
    )
    quotas = await ufaas_client.saas.enrollments.get_quotas(
        user_id=user_id,
        asset="coin",
        variant="video",
        timeout=30,
    )
    return quotas.quota


@try_except_wrapper
async def cancel_usage(video: Video):
    if video.usage_id is None:
        return

    ufaas_client = AsyncUFaaS(
        ufaas_base_url=Settings.UFAAS_BASE_URL,
        usso_base_url=Settings.USSO_BASE_URL,
        api_key=Settings.UFILES_API_KEY,
    )
    await ufaas_client.saas.usages.cancel_item(video.usage_id, timeout=30)


async def check_quota(video: Video):
    quota = await get_quota(video.user_id)
    if quota is None or quota < video.engine.price:
        raise exceptions.InsufficientFunds(
            f"You have only {quota} coins, while you need {video.engine.price} coins."
        )
