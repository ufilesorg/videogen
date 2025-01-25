from apps.video.routes import router as video_router
from fastapi_mongo_base.core import app_factory

from . import config, worker

app = app_factory.create_app(worker=worker.worker, settings=config.Settings())

app.include_router(video_router, prefix=f"{config.Settings.base_path}")
