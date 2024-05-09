import pytest
import respx
import httpx
from fastapi.testclient import TestClient

from app.core import settings
from app.core.errors import TooManyRequests
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
