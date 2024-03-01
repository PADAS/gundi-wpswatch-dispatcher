import pytest
from app.core import settings
from smartconnect import SMARTClientException
from fastapi.testclient import TestClient

from app.core.errors import TooManyRequests
from app.main import app

api_client = TestClient(app)


@pytest.mark.asyncio
async def test_process_event_v2_successfully(
    mocker,
    mock_cache,
    mock_gundi_client_v2_class,
    mock_smartclient_class,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    geoevent_v2_cloud_event_payload,
    observation_delivered_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache)
    mocker.patch("app.services.dispatchers._redis_client", mock_cache)
    mocker.patch("app.core.utils.GundiClient", mock_gundi_client_v2_class)
    mocker.patch("app.services.dispatchers.AsyncSmartClient", mock_smartclient_class)
    mocker.patch("app.core.utils.pubsub", mock_pubsub_client)
    response = api_client.post(
        "/",
        headers=pubsub_cloud_event_headers,
        json=geoevent_v2_cloud_event_payload,
    )
    assert response.status_code == 200
    # Check that the report was sent o SMART
    assert mock_smartclient_class.called
    assert mock_smartclient_class.return_value.post_smart_request.called
    # Check that the trace was written to redis db
    assert mock_cache.setex.called
    # Check that the right event was published to the right pubsub topic
    assert mock_pubsub_client.PublisherClient.called
    assert mock_pubsub_client.PubsubMessage.called
    assert mock_pubsub_client.PublisherClient.called
    assert mock_pubsub_client.PublisherClient.return_value.publish.called
    mock_pubsub_client.PublisherClient.return_value.publish.assert_any_call(
        f"projects/{settings.GCP_PROJECT_ID}/topics/{settings.DISPATCHER_EVENTS_TOPIC}",
        [observation_delivered_pubsub_message],
    )


@pytest.mark.asyncio
async def test_system_event_is_published_on_smartclient_error(
    mocker,
    mock_cache,
    mock_smartclient_class_with_400_response,
    mock_pubsub_client_with_observation_delivery_failure,
    mock_gundi_client_v2_class,
    pubsub_cloud_event_headers,
    geoevent_v2_cloud_event_payload,
    observation_delivery_failure_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache)
    mocker.patch("app.services.dispatchers._redis_client", mock_cache)
    mocker.patch("app.core.utils.GundiClient", mock_gundi_client_v2_class)
    mocker.patch(
        "app.services.dispatchers.AsyncSmartClient",
        mock_smartclient_class_with_400_response,
    )
    mocker.patch(
        "app.core.utils.pubsub", mock_pubsub_client_with_observation_delivery_failure
    )
    # Check that the dispatcher raises an exception so the message is retried later
    with pytest.raises(SMARTClientException):
        api_client.post(
            "/",
            headers=pubsub_cloud_event_headers,
            json=geoevent_v2_cloud_event_payload,
        )
    # Check that the call to send the report to SMART was made
    assert mock_smartclient_class_with_400_response.called
    assert (
        mock_smartclient_class_with_400_response.return_value.post_smart_request.called
    )
    # Check that an event was published to the right pubsub topic to inform other services about the error
    assert mock_pubsub_client_with_observation_delivery_failure.PublisherClient.called
    assert mock_pubsub_client_with_observation_delivery_failure.PubsubMessage.called
    assert mock_pubsub_client_with_observation_delivery_failure.PublisherClient.called
    assert (
        mock_pubsub_client_with_observation_delivery_failure.PublisherClient.return_value.publish.called
    )
    mock_pubsub_client_with_observation_delivery_failure.PublisherClient.return_value.publish.assert_any_call(
        f"projects/{settings.GCP_PROJECT_ID}/topics/{settings.DISPATCHER_EVENTS_TOPIC}",
        [observation_delivery_failure_pubsub_message],
    )


@pytest.mark.asyncio
async def test_throttling_on_rate_limit_exceeded(
    mocker,
    mock_cache_with_rate_limit_exceeded,
    mock_smartclient_class,
    mock_pubsub_client_with_observation_delivery_failure,
    mock_gundi_client_v2_class,
    pubsub_cloud_event_headers,
    geoevent_v2_cloud_event_payload,
    observation_delivery_failure_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache_with_rate_limit_exceeded)
    mocker.patch(
        "app.services.dispatchers._redis_client", mock_cache_with_rate_limit_exceeded
    )
    mocker.patch("app.core.utils.GundiClient", mock_gundi_client_v2_class)
    mocker.patch("app.services.dispatchers.AsyncSmartClient", mock_smartclient_class)
    mocker.patch(
        "app.core.utils.pubsub", mock_pubsub_client_with_observation_delivery_failure
    )
    # Check that the dispatcher raises an exception so the message is retried later
    with pytest.raises(TooManyRequests):
        api_client.post(
            "/",
            headers=pubsub_cloud_event_headers,
            json=geoevent_v2_cloud_event_payload,
        )
    # Check that the call to send the report to SMART was NOT made
    assert not mock_smartclient_class.return_value.post_smart_request.called
    # Check that an event was published to the right pubsub topic to inform other services about the error
    assert mock_pubsub_client_with_observation_delivery_failure.PublisherClient.called
    assert mock_pubsub_client_with_observation_delivery_failure.PubsubMessage.called
    assert mock_pubsub_client_with_observation_delivery_failure.PublisherClient.called
    assert (
        mock_pubsub_client_with_observation_delivery_failure.PublisherClient.return_value.publish.called
    )
    mock_pubsub_client_with_observation_delivery_failure.PublisherClient.return_value.publish.assert_any_call(
        f"projects/{settings.GCP_PROJECT_ID}/topics/{settings.DISPATCHER_EVENTS_TOPIC}",
        [observation_delivery_failure_pubsub_message],
    )


@pytest.mark.asyncio
async def test_process_geoevent_v1_successfully(
    mocker,
    mock_cache,
    mock_gundi_client_v1,
    mock_smartclient_class,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    geoevent_v1_cloud_event_payload,
    observation_delivered_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache)
    mocker.patch("app.services.dispatchers._redis_client", mock_cache)
    mocker.patch("app.core.utils._portal", mock_gundi_client_v1)
    mocker.patch("app.services.dispatchers.AsyncSmartClient", mock_smartclient_class)
    mocker.patch("app.core.utils.pubsub", mock_pubsub_client)
    response = api_client.post(
        "/",
        headers=pubsub_cloud_event_headers,
        json=geoevent_v1_cloud_event_payload,
    )
    assert response.status_code == 200
    # Check that the report was sent o SMART
    assert mock_smartclient_class.called
    assert mock_smartclient_class.return_value.post_smart_request.called
    # Check that the trace was written to redis db
    assert mock_cache.setex.called


@pytest.mark.asyncio
async def test_process_er_event_v1_successfully(
    mocker,
    mock_cache,
    mock_gundi_client_v1,
    mock_smartclient_class,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    er_event_v1_cloud_event_payload,
    observation_delivered_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache)
    mocker.patch("app.services.dispatchers._redis_client", mock_cache)
    mocker.patch("app.core.utils._portal", mock_gundi_client_v1)
    mocker.patch("app.services.dispatchers.AsyncSmartClient", mock_smartclient_class)
    mocker.patch("app.core.utils.pubsub", mock_pubsub_client)
    response = api_client.post(
        "/",
        headers=pubsub_cloud_event_headers,
        json=er_event_v1_cloud_event_payload,
    )
    assert response.status_code == 200
    # Check that the report was sent o SMART
    assert mock_smartclient_class.called
    assert mock_smartclient_class.return_value.post_smart_request.called
    # Check that the trace was written to redis db
    assert mock_cache.setex.called


@pytest.mark.asyncio
async def test_process_er_event_v1_with_attachment_successfully(
    mocker,
    mock_cache,
    mock_gundi_client_v1,
    mock_smartclient_class,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    mock_cloud_storage_client_class,
    er_event_v1_with_attachment_cloud_event_payload,
    observation_delivered_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache)
    mocker.patch("app.services.dispatchers._redis_client", mock_cache)
    mocker.patch("app.core.utils._portal", mock_gundi_client_v1)
    mocker.patch("app.services.dispatchers.AsyncSmartClient", mock_smartclient_class)
    mocker.patch("app.services.dispatchers.Storage", mock_cloud_storage_client_class)
    mocker.patch("app.core.utils.pubsub", mock_pubsub_client)
    response = api_client.post(
        "/",
        headers=pubsub_cloud_event_headers,
        json=er_event_v1_with_attachment_cloud_event_payload,
    )
    assert response.status_code == 200
    # Check that the attachment was downloaded from cloud storage
    assert mock_cloud_storage_client_class.return_value.download.called
    # Check that the report was sent o SMART
    assert mock_smartclient_class.called
    assert mock_smartclient_class.return_value.post_smart_request.called


@pytest.mark.asyncio
async def test_process_er_patrol_v1_successfully(
    mocker,
    mock_cache,
    mock_gundi_client_v1,
    mock_smartclient_class,
    mock_pubsub_client,
    pubsub_cloud_event_headers,
    er_patrol_v1_cloud_event_payload,
    observation_delivered_pubsub_message,
):
    # Mock external dependencies
    mocker.patch("app.core.utils._cache_db", mock_cache)
    mocker.patch("app.services.dispatchers._redis_client", mock_cache)
    mocker.patch("app.core.utils._portal", mock_gundi_client_v1)
    mocker.patch("app.services.dispatchers.AsyncSmartClient", mock_smartclient_class)
    mocker.patch("app.core.utils.pubsub", mock_pubsub_client)
    response = api_client.post(
        "/",
        headers=pubsub_cloud_event_headers,
        json=er_patrol_v1_cloud_event_payload,
    )
    assert response.status_code == 200
    # Check that the report was sent o SMART
    assert mock_smartclient_class.called
    assert mock_smartclient_class.return_value.post_smart_request.called
    # Check that the trace was written to redis db
    assert mock_cache.setex.called
