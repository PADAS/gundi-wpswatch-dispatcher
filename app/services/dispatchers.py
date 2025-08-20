import mimetypes
import os
from unittest.mock import AsyncMock

import httpx
import logging
from app.core import settings
from urllib.parse import urlparse
from gundi_core import schemas
from gcloud.aio.storage import Storage
from app.core.utils import RateLimiterSemaphore, redis_client, find_config_for_action

if settings.GCP_ENVIRONMENT_ENABLED:
    gcp_storage = Storage()
else:
    gcp_storage = AsyncMock()  # Mock for CI/Test environment


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


class WPSWatchImageDispatcher:
    def __init__(self, integration):
        self.integration = integration

    async def _wpswatch_post(self, request_data, file_name, file_data):
        # Look for the configuration of the authentication action
        configurations = self.integration.configurations
        integration_action_config = find_config_for_action(
            configurations=configurations,
            action_value=schemas.v2.WPSWatchActions.AUTHENTICATE.value,
        )
        if not integration_action_config:
            raise ValueError(
                f"Authentication settings for integration {str(self.integration.id)} are missing. Please fix the integration setup in the portal."
            )
        api_key = integration_action_config.data.get("api_key")
        if not api_key:
            raise ValueError(
                f"Token for integration {str(self.integration.id)} is missing. Please fix the integration setup in the portal."
            )
        headers = {
            "Wps-Api-Key": api_key,
        }
        files = {"Attachment1": (file_name, file_data)}
        parsed_url = urlparse(self.integration.base_url)
        sanitized_endpoint = f"{parsed_url.scheme}://{parsed_url.hostname}/api/Upload"
        try:
            connect_timeout, read_timeout = settings.DEFAULT_REQUESTS_TIMEOUT
            timeout_settings = httpx.Timeout(read_timeout, connect=connect_timeout)
            async with httpx.AsyncClient(timeout=timeout_settings) as client:
                response = await client.post(
                    sanitized_endpoint,
                    data=request_data,
                    headers=headers,
                    files=files,
                )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.exception(
                f"Error occurred posting to WPS Watch Site {sanitized_endpoint} \n {type(e)}: {e}"
            )
            raise e  # Raise so it's retried
        return response

    async def send(self, image: schemas.v2.WPSWatchImage, **kwargs):
        related_event = kwargs.get("related_event")
        if not related_event:
            raise ValueError("related_observation is required")
        camera_id = related_event.camera_id
        if not camera_id:
            raise ValueError("camera_id is required")

        try:  # Download the Image from GCP
            file_path = image.file_path
            downloaded_file = await gcp_storage.download(
                bucket=settings.BUCKET_NAME, object_name=file_path
            )
        except Exception as e:
            logger.exception(
                f"Error downloading file '{file_path}' from cloud storage: {type(e)}: {e}"
            )
            raise e

        # Get the upload domain
        configurations = self.integration.configurations
        integration_push_config = find_config_for_action(
            configurations=configurations,
            action_value=schemas.v2.WPSWatchActions.PUSH_EVENTS.value,
        )
        if integration_push_config and (
            upload_domain := integration_push_config.data.get("upload_domain")
        ):
            wpswatch_upload_domain = upload_domain
        else:
            wpswatch_upload_domain = "upload.wpswatch.org"  # Default

        try:  # Send the image to WPS Watch
            async with RateLimiterSemaphore(
                redis_client=redis_client, url=str(self.integration.base_url)
            ):
                request_data = {
                    "From": "gundiservice.org",
                    "To": f"{camera_id}@{wpswatch_upload_domain}",
                }
                file_name = os.path.basename(file_path)
                result = await self._wpswatch_post(
                    request_data=request_data,
                    file_name=file_name,
                    file_data=downloaded_file,
                )
        except Exception as e:
            logger.exception(f"Error sending data to WPS Watch {e}")
            raise e
        else:
            logger.info(f"File {file_path} delivered to WPS Watch with success.")
            # Remove the file from GCP after delivering it to WPS Watch
            if settings.DELETE_FILES_AFTER_DELIVERY:
                await gcp_storage.delete(
                    bucket=settings.BUCKET_NAME, object_name=file_path
                )
                logger.debug(f"File {file_path} deleted from GCP.")
            return result


dispatcher_cls_by_type = {
    # Gundi v1
    schemas.v1.StreamPrefixEnum.camera_trap: WPSWatchCameraTrapDispatcher,
}
