import mimetypes
import os
import httpx
import logging
from app.core import settings
from urllib.parse import urlparse
from gundi_core import schemas
from gcloud.aio.storage import Storage
from app.core.utils import RateLimiterSemaphore, redis_client

gcp_storage = Storage()


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = (3.1, 20)


########################################################################################
# GUNDI V1
########################################################################################


class WPSWatchCameraTrapDispatcher:
    def __init__(self, config: schemas.OutboundConfiguration):
        self.config = config

    async def send(self, camera_trap_payload: dict):
        try:
            file_name = camera_trap_payload.get("Attachment1")
            downloaded_file = await gcp_storage.download(
                bucket=settings.BUCKET_NAME, object_name=file_name
            )
            file_data = self.get_file_data(file_name, downloaded_file)
            async with RateLimiterSemaphore(
                redis_client=redis_client, url=str(self.config.endpoint)
            ):
                result = await self.wpswatch_post(camera_trap_payload, file_data)
        except Exception as e:
            logger.exception(f"Error sending data to WPS Watch {e}")
            raise e
        else:
            logger.info(f"File {file_name} delivered to WPS Watch with success.")
            # Remove the file from GCP after delivering it to WPS Watch
            if settings.DELETE_FILES_AFTER_DELIVERY:
                await gcp_storage.delete(
                    bucket=settings.BUCKET_NAME, object_name=file_name
                )
                logger.debug(f"File {file_name} deleted from GCP.")
            return result

    # ToDo: Make a WPS Watch client class?
    async def wpswatch_post(self, camera_trap_payload, file_data=None):
        sanitized_endpoint = self.sanitize_endpoint(
            f"{self.config.endpoint}/api/Upload"
        )
        headers = {
            "Wps-Api-Key": self.config.token,
        }
        files = {"Attachment1": file_data}

        body = camera_trap_payload
        try:
            connect_timeout, read_timeout = settings.DEFAULT_REQUESTS_TIMEOUT
            timeout_settings = httpx.Timeout(read_timeout, connect=connect_timeout)
            async with httpx.AsyncClient(timeout=timeout_settings) as client:
                response = await client.post(
                    sanitized_endpoint,
                    data=body,
                    headers=headers,
                    files=files,
                )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.exception(f"Error occurred posting to WPS Watch {e}", extra=body)
            raise e  # Raise so it's retried
        return response

    def get_file_data(self, file_name, file):
        name, file_ext = os.path.splitext(file_name)
        mimetype = mimetypes.types_map[file_ext]
        return file_name, file, mimetype

    @staticmethod
    def sanitize_endpoint(endpoint):
        scheme = urlparse(endpoint).scheme
        host = urlparse(endpoint).hostname
        path = urlparse(endpoint).path.replace(
            "//", "/"
        )  # in case tailing forward slash configured in portal
        sanitized_endpoint = f"{scheme}://{host}{path}"
        return sanitized_endpoint


dispatcher_cls_by_type = {
    # Gundi v1
    schemas.v1.StreamPrefixEnum.camera_trap: WPSWatchCameraTrapDispatcher,
}
