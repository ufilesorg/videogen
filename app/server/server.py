import logging

from apps.video.routes import router as video_router
from fastapi_mongo_base.core import app_factory

from . import config, worker

config.Settings.config_logger()
settings = config.Settings()

logging.info(f"Starting server on {config.Settings.base_path}")

app = app_factory.create_app(worker=worker.worker, settings=config.Settings())

app.include_router(video_router, prefix=f"{config.Settings.base_path}")

logging.info("\n".join([route.path for route in app.routes]))
