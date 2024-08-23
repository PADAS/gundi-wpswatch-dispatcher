import base64
import json
import pytest
import respx
import httpx
from fastapi.testclient import TestClient
from gundi_core import schemas
from app.core import settings
from app.core.errors import TooManyRequests
from app.core.utils import find_config_for_action
from app.main import app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_headers,process_msg_expected",
    [
        ("pubsub_cloud_event_headers", True),
        ("pubsub_cloud_event_headers_with_future_timestamp", True),
        ("pubsub_cloud_event_headers_with_old_timestamp", False),
    ],
)
async def test_process_cameratrap_file_successfully(
    request,
    process_msg_expected,
    mocker,
    mock_redis,
    mock_gundi_client_v1,
    mock_cloud_storage_client,
    mock_pubsub_client,
    event_headers,
    cameratrap_v1_cloud_event_payload,
    camera_trap_upload_response,
):
    event_headers = request.getfixturevalue(event_headers)
    # Mock external dependencies
    mocker.patch("app.core.gundi.portal_client", mock_gundi_client_v1)
    mocker.patch("app.core.gundi.redis_client", mock_redis)
    mocker.patch("app.core.utils.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(
        base_url="https://wpswatch-api.test.com", assert_all_called=False
    ) as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file").respond(
            httpx.codes.OK
        )
        with TestClient(
            app
        ) as api_client:  # Use as context manager to trigger lifespan hooks
            response = api_client.post(
                "/",
                headers=event_headers,
                json=cameratrap_v1_cloud_event_payload,
            )
            assert response.status_code == 200
        # Check that the wpswatch api was called
        assert route.called == process_msg_expected
        # Check that the file was retrieved and deleted from GCP
        assert mock_cloud_storage_client.download.called == process_msg_expected
        if (
            mock_cloud_storage_client.download.called
            and settings.DELETE_FILES_AFTER_DELIVERY
        ):
            assert mock_cloud_storage_client.delete.called


@pytest.mark.asyncio
async def test_raises_on_wpswatch_api_bad_status(
    mocker,
    mock_redis,
    mock_gundi_client_v1,
    mock_cloud_storage_client,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    cameratrap_v1_cloud_event_payload,
):
    # Mock external dependencies
    mocker.patch("app.core.gundi.portal_client", mock_gundi_client_v1)
    mocker.patch("app.core.gundi.redis_client", mock_redis)
    mocker.patch("app.core.utils.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(base_url="https://wpswatch-api.test.com") as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file").respond(
            httpx.codes.BAD_REQUEST
        )
        with pytest.raises(
            httpx.HTTPStatusError
        ):  # Exception makes GCP retry the message
            with TestClient(
                app
            ) as api_client:  # Use as context manager to trigger lifespan hooks
                # Call the dispatcher with a PubSub message
                response = api_client.post(
                    "/",
                    headers=pubsub_cloud_event_headers,
                    json=cameratrap_v1_cloud_event_payload,
                )
        # Check that the wpswatch api was called
        assert route.called
        # Check that the file was retrieved but Not deleted
        assert mock_cloud_storage_client.download.called
        assert not mock_cloud_storage_client.delete.called


@pytest.mark.asyncio
async def test_raises_on_wpswatch_api_timeout(
    mocker,
    mock_redis,
    mock_gundi_client_v1,
    mock_cloud_storage_client,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    cameratrap_v1_cloud_event_payload,
):
    # Mock external dependencies
    mocker.patch("app.core.gundi.portal_client", mock_gundi_client_v1)
    mocker.patch("app.core.gundi.redis_client", mock_redis)
    mocker.patch("app.core.utils.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(base_url="https://wpswatch-api.test.com") as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file")
        route.side_effect = httpx.TimeoutException
        with pytest.raises(
            httpx.TimeoutException
        ):  # Exception makes GCP retry the message
            with TestClient(
                app
            ) as api_client:  # Use as context manager to trigger lifespan hooks
                # Call the dispatcher with a PubSub message
                response = api_client.post(
                    "/",
                    headers=pubsub_cloud_event_headers,
                    json=cameratrap_v1_cloud_event_payload,
                )
        # Check that the wpswatch api was called
        assert route.called
        # Check that the file was retrieved but Not deleted
        assert mock_cloud_storage_client.download.called
        assert not mock_cloud_storage_client.delete.called


@pytest.mark.asyncio
async def test_throttling_on_rate_limit_exceeded(
    mocker,
    mock_redis_with_rate_limit_exceeded,
    mock_gundi_client_v1,
    mock_cloud_storage_client,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    cameratrap_v1_cloud_event_payload,
):
    # Mock external dependencies
    # Mock external dependencies
    mocker.patch("app.core.gundi.portal_client", mock_gundi_client_v1)
    mocker.patch("app.core.gundi.redis_client", mock_redis_with_rate_limit_exceeded)
    mocker.patch("app.core.utils.redis_client", mock_redis_with_rate_limit_exceeded)
    mocker.patch(
        "app.services.dispatchers.redis_client", mock_redis_with_rate_limit_exceeded
    )
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(
        base_url="https://wpswatch-api.test.com", assert_all_called=False
    ) as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file").respond(
            httpx.codes.OK
        )
        # Check that the dispatcher raises an exception so the message is retried later
        with pytest.raises(TooManyRequests):
            with TestClient(
                app
            ) as api_client:  # Use as context manager to trigger lifespan hooks
                api_client.post(
                    "/",
                    headers=pubsub_cloud_event_headers,
                    json=cameratrap_v1_cloud_event_payload,
                )
    # Check that the wpswatch api was NOT called
    assert not route.called
    # Check that the file was retrieved but Not deleted
    assert mock_cloud_storage_client.download.called
    assert not mock_cloud_storage_client.delete.called


@pytest.mark.asyncio
async def test_process_event_v2_successfully(
    mocker,
    mock_redis,
    mock_gundi_client_v2_class,
    mock_cloud_storage_client,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    event_v2_cloud_event_payload,
    destination_integration_v2,
):

    # Mock external dependencies
    mocker.patch("app.core.gundi.GundiClient", mock_gundi_client_v2_class)
    mocker.patch("app.core.gundi.redis_client", mock_redis)
    mocker.patch("app.core.utils.redis_client", mock_redis)
    mocker.patch("app.core.system_events.pubsub", mock_pubsub_client)
    mocker.patch("app.services.event_handlers._cache_db", mock_redis)
    mocker.patch("app.services.dispatchers.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(
        base_url=destination_integration_v2.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file").respond(
            httpx.codes.OK
        )
        with TestClient(
            app
        ) as api_client:  # Use as context manager to trigger lifespan hooks
            response = api_client.post(
                "/",
                headers=pubsub_cloud_event_headers,
                json=event_v2_cloud_event_payload,
            )
            assert response.status_code == 200

        # Check that the event was cached until receiving the attachment
        gundi_id = event_v2_cloud_event_payload["message"]["attributes"]["gundi_id"]
        destination_id = event_v2_cloud_event_payload["message"]["attributes"][
            "destination_id"
        ]
        event_data = event_v2_cloud_event_payload["message"]["data"]
        decoded_event_data = json.loads(base64.b64decode(event_data))
        serialized_payload = json.dumps(decoded_event_data["payload"], default=str)
        mock_redis.setex.assert_called_with(
            name=f"wps_image_metadata.{gundi_id}.{destination_id}",
            time=settings.IMAGE_METADATA_CACHE_TTL,
            value=serialized_payload,
        )
        # Check that the wpswatch api was Not called
        assert not route.called


@pytest.mark.asyncio
async def test_process_attachment_v2_successfully(
    mocker,
    mock_redis,
    mock_redis_with_cached_event,
    mock_gundi_client_v2_class,
    mock_cloud_storage_client,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    event_v2_cloud_event_payload,
    attachment_v2_cloud_event_payload,
    attachment_file_blob,
    destination_integration_v2,
):
    # Mock external dependencies
    mocker.patch("app.core.gundi.GundiClient", mock_gundi_client_v2_class)
    mocker.patch("app.core.gundi.redis_client", mock_redis)
    mocker.patch("app.core.utils.redis_client", mock_redis)
    mocker.patch("app.core.system_events.pubsub", mock_pubsub_client)
    mocker.patch("app.services.event_handlers._cache_db", mock_redis_with_cached_event)
    mocker.patch("app.services.dispatchers.redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    # Mock the WPSWatch API
    async with respx.mock(
        base_url=destination_integration_v2.base_url,
        assert_all_called=True,
        assert_all_mocked=True,
    ) as respx_mock:
        # Define the expected request:

        # Camera ID is taken from the related event source id
        event_data = event_v2_cloud_event_payload["message"]["data"]
        decoded_event_data = json.loads(base64.b64decode(event_data))
        camera_id = decoded_event_data["payload"]["camera_id"]

        # Upload domain is stored in a config
        configurations = destination_integration_v2.configurations
        push_config = find_config_for_action(
            configurations=configurations,
            action_value=schemas.v2.WPSWatchActions.PUSH_EVENTS.value,
        )
        wpswatch_upload_domain = push_config.data.get("upload_domain")
        expected_data = {
            "From": "gundiservice.org",
            "To": f"{camera_id}@{wpswatch_upload_domain}",
        }

        # API Key is stored in a config
        auth_config = find_config_for_action(
            configurations=configurations,
            action_value=schemas.v2.WPSWatchActions.AUTHENTICATE.value,
        )
        api_key = auth_config.data.get("api_key")
        expected_headers = {"Wps-Api-Key": api_key}

        expected_files = {
            "Attachment1": (
                "7687a8d5-a89d-4ceb-be3b-5e1e3b7dc1a9_elephant.jpg",
                attachment_file_blob,
            )
        }

        # Patch the upload endpoint
        route = respx_mock.post(
            "api/Upload",
            headers=expected_headers,
            data=expected_data,
            files=expected_files,
        ).respond(httpx.codes.OK)
        with TestClient(
            app
        ) as api_client:  # Use as context manager to trigger lifespan hooks
            response = api_client.post(
                "/",
                headers=pubsub_cloud_event_headers,
                json=attachment_v2_cloud_event_payload,
            )
            assert response.status_code == 200
            assert route.called
