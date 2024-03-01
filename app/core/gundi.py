import logging
from uuid import UUID
import httpx
from gundi_core import schemas
from app.core import settings
from app.core.utils import ExtraKeys
from app.core.errors import ReferenceDataError
from gundi_client import PortalApi
from .utils import _cache_db

logger = logging.getLogger(__name__)


DEFAULT_LOCATION = schemas.Location(x=0.0, y=0.0)
GUNDI_V1 = "v1"
GUNDI_V2 = "v2"

connect_timeout, read_timeout = settings.DEFAULT_REQUESTS_TIMEOUT
_portal = PortalApi(connect_timeout=connect_timeout, data_timeout=read_timeout)
_cache_ttl = settings.PORTAL_CONFIG_OBJECT_CACHE_TTL


async def get_outbound_config_detail(
    outbound_id: UUID,
) -> schemas.OutboundConfiguration:
    if not outbound_id:
        raise ValueError("integration_id must not be None")

    extra_dict = {
        ExtraKeys.AttentionNeeded: True,
        ExtraKeys.OutboundIntId: str(outbound_id),
    }

    cache_key = f"outbound_detail.{outbound_id}"
    cached = await _cache_db.get(cache_key)

    if cached:
        config = schemas.OutboundConfiguration.parse_raw(cached)
        logger.debug(
            "Using cached outbound integration detail",
            extra={
                **extra_dict,
                ExtraKeys.AttentionNeeded: False,
                "outbound_detail": config,
            },
        )
        return config

    logger.debug(f"Cache miss for outbound integration detail", extra={**extra_dict})

    try:
        response = await _portal.get_outbound_integration(
            integration_id=str(outbound_id)
        )
    except httpx.HTTPStatusError as e:
        error = f"HTTPStatusError: {e.response.status_code}, {e.response.text}"
        message = (
            f"Failed to get outbound details for outbound_id {outbound_id}: {error}"
        )
        target_url = str(e.request.url)
        logger.exception(
            message,
            extra={
                **extra_dict,
                ExtraKeys.AttentionNeeded: True,
                ExtraKeys.Url: target_url,
            },
        )
        # Raise again so it's retried later
        raise ReferenceDataError(message)
    except httpx.HTTPError as e:
        error = f"HTTPError: {e}"
        message = (
            f"Failed to get outbound details for outbound_id {outbound_id}: {error}"
        )
        target_url = str(e.request.url)
        logger.exception(
            message,
            extra={
                **extra_dict,
                ExtraKeys.AttentionNeeded: True,
                ExtraKeys.Url: target_url,
            },
        )
        # Raise again so it's retried later
        raise ReferenceDataError(message)
    else:
        try:
            config = schemas.OutboundConfiguration.parse_obj(response)
        except Exception:
            logger.error(
                f"Failed decoding response for Outbound Integration Detail",
                extra={**extra_dict, "resp_text": response},
            )
            raise ReferenceDataError(
                "Failed decoding response for Outbound Integration Detail"
            )
        else:
            if config:  # don't cache empty response
                await _cache_db.setex(cache_key, _cache_ttl, config.json())
            return config


async def get_inbound_integration_detail(
    integration_id: UUID,
) -> schemas.IntegrationInformation:
    if not integration_id:
        raise ValueError("integration_id must not be None")

    extra_dict = {
        ExtraKeys.AttentionNeeded: True,
        ExtraKeys.InboundIntId: str(integration_id),
    }

    cache_key = f"inbound_detail.{integration_id}"
    cached = await _cache_db.get(cache_key)

    if cached:
        config = schemas.IntegrationInformation.parse_raw(cached)
        logger.debug(
            "Using cached inbound integration detail",
            extra={**extra_dict, "integration_detail": config},
        )
        return config

    logger.debug(f"Cache miss for inbound integration detai", extra={**extra_dict})

    try:
        response = await _portal.get_inbound_integration(
            integration_id=str(integration_id)
        )
    except httpx.HTTPStatusError as e:
        error = f"HTTPStatusError: {e.response.status_code}, {e.response.text}"
        message = f"Failed to get inbound details for integration_id {integration_id}: {error}"
        target_url = str(e.request.url)
        logger.exception(
            message,
            extra={
                **extra_dict,
                ExtraKeys.AttentionNeeded: True,
                ExtraKeys.Url: target_url,
            },
        )
        # Raise again so it's retried later
        raise ReferenceDataError(message)
    except httpx.HTTPError as e:
        error = f"HTTPError: {e}"
        message = f"Failed to get inbound details for integration_id {integration_id}: {error}"
        target_url = str(e.request.url)
        logger.exception(
            message,
            extra={
                **extra_dict,
                ExtraKeys.AttentionNeeded: True,
                ExtraKeys.Url: target_url,
            },
        )
        # Raise again so it's retried later
        raise ReferenceDataError(message)
    else:
        try:
            config = schemas.IntegrationInformation.parse_obj(response)
        except Exception:
            logger.error(
                f"Failed decoding response for InboundIntegration Detail",
                extra={**extra_dict, "resp_text": response},
            )
            raise ReferenceDataError(
                "Failed decoding response for InboundIntegration Detail"
            )
        else:
            if config:  # don't cache empty response
                await _cache_db.setex(cache_key, _cache_ttl, config.json())
            return config
