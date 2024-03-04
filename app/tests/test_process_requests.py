import pytest
import respx
import httpx
from fastapi.testclient import TestClient
from app.core.errors import TooManyRequests
from app.main import app

api_client = TestClient(app)


@pytest.mark.asyncio
async def test_process_cameratrap_file_successfully(
    mocker,
    mock_redis,
    mock_gundi_client_v1,
    mock_cloud_storage_client,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    cameratrap_v1_cloud_event_payload,
    camera_trap_upload_response,
):
    # Mock external dependencies
    mocker.patch("app.core.gundi._portal", mock_gundi_client_v1)
    mocker.patch("app.core.gundi._cache_db", mock_redis)
    mocker.patch("app.services.dispatchers._redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(base_url="https://wpswatch-api.test.com") as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file").respond(
            httpx.codes.OK
        )
        response = api_client.post(
            "/",
            headers=pubsub_cloud_event_headers,
            json=cameratrap_v1_cloud_event_payload,
        )
        assert response.status_code == 200
        # Check that the wpswatch api was called
        assert route.called
        # Check that the file was retrieved and deleted from GCP
        assert mock_cloud_storage_client.download.called
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
    mocker.patch("app.core.gundi._portal", mock_gundi_client_v1)
    mocker.patch("app.core.gundi._cache_db", mock_redis)
    mocker.patch("app.services.dispatchers._redis_client", mock_redis)
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
    mocker.patch("app.core.gundi._portal", mock_gundi_client_v1)
    mocker.patch("app.core.gundi._cache_db", mock_redis)
    mocker.patch("app.services.dispatchers._redis_client", mock_redis)
    mocker.patch("app.services.dispatchers.gcp_storage", mock_cloud_storage_client)
    mocker.patch("app.services.process_messages.pubsub", mock_pubsub_client)
    async with respx.mock(base_url="https://wpswatch-api.test.com") as respx_mock:
        # Mock the WPSWatch API response
        route = respx_mock.post(f"api/Upload", name="upload_file")
        route.side_effect = httpx.TimeoutException
        with pytest.raises(
            httpx.TimeoutException
        ):  # Exception makes GCP retry the message
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
    mocker.patch("app.core.gundi._portal", mock_gundi_client_v1)
    mocker.patch("app.core.gundi._cache_db", mock_redis_with_rate_limit_exceeded)
    mocker.patch(
        "app.services.dispatchers._redis_client", mock_redis_with_rate_limit_exceeded
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
