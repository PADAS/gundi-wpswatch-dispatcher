import json
import logging
import aiohttp
from datetime import datetime, timezone
from gcloud.aio import pubsub
from gundi_core.schemas.v2 import StreamPrefixEnum
from opentelemetry.trace import SpanKind
from app.core import settings
from app.core.utils import (
    extract_fields_from_message,
    ExtraKeys,
)
from app.core.gundi import (
    get_outbound_config_detail,
    get_inbound_integration_detail,
)
from app.core.errors import DispatcherException, ReferenceDataError, TooManyRequests
from app.core import tracing
from . import dispatchers
from .event_handlers import event_handlers, event_schemas


logger = logging.getLogger(__name__)


def get_dlq_topic_for_data_type(data_type: StreamPrefixEnum) -> str:
    if data_type == StreamPrefixEnum.observation:
        return settings.OBSERVATIONS_DEAD_LETTER_TOPIC
    elif data_type == StreamPrefixEnum.event:
        return settings.EVENTS_DEAD_LETTER_TOPIC
    elif data_type == StreamPrefixEnum.event_update:
        return settings.EVENTS_UPDATES_DEAD_LETTER_TOPIC
    elif data_type == StreamPrefixEnum.attachment:
        return settings.ATTACHMENTS_DEAD_LETTER_TOPIC
    elif data_type == StreamPrefixEnum.text_message:
        return settings.TEXT_MESSAGES_DEAD_LETTER_TOPIC
    else:
        return settings.LEGACY_DEAD_LETTER_TOPIC


async def send_observation_to_dead_letter_topic(transformed_observation, attributes):
    with tracing.tracer.start_as_current_span(
        "send_message_to_dead_letter_topic", kind=SpanKind.CLIENT
    ) as current_span:

        print(f"Forwarding observation to dead letter topic: {transformed_observation}")
        # Publish to another PubSub topic
        connect_timeout, read_timeout = settings.DEFAULT_REQUESTS_TIMEOUT
        timeout_settings = aiohttp.ClientTimeout(
            sock_connect=connect_timeout, sock_read=read_timeout
        )
        async with aiohttp.ClientSession(
            raise_for_status=True, timeout=timeout_settings
        ) as session:
            client = pubsub.PublisherClient(session=session)
            # Get the topic
            if attributes.get("gundi_version", "v1") == "v2":
                topic_name = get_dlq_topic_for_data_type(
                    data_type=attributes.get("stream_type")
                )
            else:
                topic_name = settings.LEGACY_DEAD_LETTER_TOPIC
            current_span.set_attribute("topic", topic_name)
            topic = client.topic_path(settings.GCP_PROJECT_ID, topic_name)
            # Prepare the payload
            binary_payload = json.dumps(transformed_observation, default=str).encode(
                "utf-8"
            )
            messages = [pubsub.PubsubMessage(binary_payload, **attributes)]
            logger.info(f"Sending observation to PubSub topic {topic_name}..")
            try:  # Send to pubsub
                response = await client.publish(topic, messages)
            except Exception as e:
                logger.exception(
                    f"Error sending observation to dead letter topic {topic_name}: {e}. Please check if the topic exists or review settings."
                )
                raise e
            else:
                logger.info(f"Observation sent to the dead letter topic successfully.")
                logger.debug(f"GCP PubSub response: {response}")

        current_span.set_attribute("is_sent_to_dead_letter_queue", True)
        current_span.add_event(
            name="routing_service.observation_sent_to_dead_letter_queue"
        )


async def dispatch_transformed_observation_v1(
    stream_type: str, outbound_config_id: str, inbound_int_id: str, observation
):
    extra_dict = {
        ExtraKeys.OutboundIntId: outbound_config_id,
        ExtraKeys.InboundIntId: inbound_int_id,
        ExtraKeys.Observation: observation,
        ExtraKeys.StreamType: stream_type,
    }

    if not outbound_config_id:
        error_msg = (
            f"No destination set for the observation {observation}. Discarded.",
        )
        logger.error(
            error_msg,
            extra=extra_dict,
        )
        raise DispatcherException(error_msg)

    # Get details about the destination
    config = await get_outbound_config_detail(outbound_config_id)
    inbound_integration = await get_inbound_integration_detail(inbound_int_id)
    provider_key = inbound_integration.provider

    if not config:
        error_msg = f"No destination config details found for {outbound_config_id}"
        logger.error(
            error_msg,
            extra={**extra_dict, ExtraKeys.AttentionNeeded: True},
        )
        raise ReferenceDataError(error_msg)

    try:  # Select the dispatcher
        dispatcher_cls = dispatchers.dispatcher_cls_by_type[stream_type]
    except KeyError as e:
        error_msg = f"No dispatcher found for stream type {stream_type}"
        logger.exception(
            error_msg,
            extra={
                **extra_dict,
                ExtraKeys.AttentionNeeded: True,
            },
        )
        raise DispatcherException(error_msg)
    else:  # Send the observation to the destination
        try:
            dispatcher = dispatcher_cls(config)
            result = await dispatcher.send(observation)
        except Exception as e:
            logger.exception(
                f"Exception occurred dispatching observation",
                extra={
                    **extra_dict,
                    ExtraKeys.Provider: provider_key,
                    ExtraKeys.AttentionNeeded: True,
                },
            )
            raise e


async def process_transformed_observation_v1(transformed_message, attributes):
    with tracing.tracer.start_as_current_span(
        "wpswatch_dispatcher.process_transformed_observation", kind=SpanKind.CLIENT
    ) as current_span:
        current_span.add_event(
            name="wpswatch_dispatcher.transformed_observation_received_at_dispatcher"
        )
        observation_type = attributes.get("observation_type")
        if observation_type not in dispatchers.dispatcher_cls_by_type.keys():
            error_msg = (
                f"Stream type `{observation_type}` is not supported by this dispatcher."
            )
            logger.error(
                error_msg,
                extra={
                    ExtraKeys.AttentionNeeded: True,
                },
            )
            raise DispatcherException(
                f"Exception occurred dispatching observation: {error_msg}"
            )

        provider_key = transformed_message.pop(
            "provider_key", attributes.get("provider_key")
        )
        gundi_id = attributes.get("gundi_id")
        related_to = attributes.get("related_to")
        device_id = attributes.get("device_id")
        integration_id = attributes.get("integration_id")
        outbound_config_id = attributes.get("outbound_config_id")
        logger.debug(f"transformed_observation: {transformed_message}")
        logger.info(
            f"Received transformed observation",
            extra={
                ExtraKeys.DeviceId: device_id,
                ExtraKeys.InboundIntId: integration_id,
                ExtraKeys.Provider: provider_key,
                ExtraKeys.OutboundIntId: outbound_config_id,
                ExtraKeys.StreamType: observation_type,
                ExtraKeys.GundiId: gundi_id,
                ExtraKeys.RelatedTo: related_to,
            },
        )
        current_span.set_attribute("transformed_message", str(transformed_message))
        current_span.set_attribute("environment", settings.TRACE_ENVIRONMENT)
        current_span.set_attribute("service", "cdip-routing")

        logger.debug(f"transformed_observation: {transformed_message}")
        logger.info(
            "received transformed observation",
            extra={
                ExtraKeys.DeviceId: device_id,
                ExtraKeys.InboundIntId: integration_id,
                ExtraKeys.OutboundIntId: outbound_config_id,
                ExtraKeys.StreamType: observation_type,
            },
        )

        logger.info(
            "Dispatching for transformed observation.",
            extra={
                ExtraKeys.InboundIntId: integration_id,
                ExtraKeys.OutboundIntId: outbound_config_id,
                ExtraKeys.StreamType: observation_type,
            },
        )
        with tracing.tracer.start_as_current_span(
            "wpswatch_dispatcher.dispatch_transformed_observation", kind=SpanKind.CLIENT
        ) as subspan:
            try:
                await dispatch_transformed_observation_v1(
                    observation_type,
                    outbound_config_id,
                    integration_id,
                    transformed_message,
                )
                subspan.set_attribute("is_dispatched_successfully", True)
                subspan.set_attribute("destination_id", str(outbound_config_id))
                subspan.add_event(
                    name="wpswatch_dispatcher.observation_dispatched_successfully"
                )
            except (DispatcherException, ReferenceDataError) as e:
                error_msg = f"External error occurred processing transformed observation {gundi_id}: {e}"
                logger.exception(
                    error_msg,
                    extra={
                        ExtraKeys.AttentionNeeded: True,
                        ExtraKeys.DeviceId: device_id,
                        ExtraKeys.InboundIntId: integration_id,
                        ExtraKeys.OutboundIntId: outbound_config_id,
                        ExtraKeys.GundiId: gundi_id,
                        ExtraKeys.StreamType: observation_type,
                    },
                )
                subspan.set_attribute("error", error_msg)
                # Raise the exception so the message is retried later by GCP
                raise e
            except TooManyRequests as e:
                error_msg = f"Throttling request {gundi_id}: {e}"
                logger.exception(
                    error_msg,
                    extra={
                        ExtraKeys.AttentionNeeded: True,
                        ExtraKeys.DeviceId: device_id,
                        ExtraKeys.InboundIntId: integration_id,
                        ExtraKeys.OutboundIntId: outbound_config_id,
                        ExtraKeys.GundiId: gundi_id,
                        ExtraKeys.StreamType: observation_type,
                    },
                )
                subspan.set_attribute("is_throttled", True)
                subspan.add_event(name="wpswatch_dispatcher.observation_throttled")
                # Raise the exception so the message is retried later by GCP
                raise e
            except Exception as e:
                error_msg = (
                    f"Error occurred processing transformed observation {gundi_id}: {e}"
                )
                logger.exception(
                    error_msg,
                    extra={
                        ExtraKeys.AttentionNeeded: True,
                        ExtraKeys.DeadLetter: True,
                        ExtraKeys.DeviceId: device_id,
                        ExtraKeys.GundiId: gundi_id,
                        ExtraKeys.InboundIntId: integration_id,
                        ExtraKeys.OutboundIntId: outbound_config_id,
                        ExtraKeys.StreamType: observation_type,
                    },
                )
                subspan.set_attribute("error", error_msg)
                # Raise the exception so the message is retried later by GCP
                raise e


def is_too_old(timestamp):
    if not timestamp:
        return False
    try:  # The timestamp does not always include the microseconds part
        event_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        event_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    event_time = event_time.replace(tzinfo=timezone.utc)
    current_time = datetime.now(timezone.utc)
    # Notice: We have seen cloud events with future timestamps. Don't use .seconds
    event_age_seconds = (current_time - event_time).total_seconds()
    return event_age_seconds > settings.MAX_EVENT_AGE_SECONDS


async def process_transformer_event_v2(raw_event, attributes):
    with tracing.tracer.start_as_current_span(
        "wpswatch_dispatcher.process_transformer_event_v2", kind=SpanKind.CLIENT
    ) as current_span:
        current_span.add_event(
            name="wpswatch_dispatcher.transformed_observation_received_at_dispatcher"
        )
        current_span.set_attribute("transformed_message", str(raw_event))
        current_span.set_attribute("environment", settings.TRACE_ENVIRONMENT)
        current_span.set_attribute("service", "er-dispatcher")
        logger.debug(
            f"Message received: \npayload: {raw_event} \nattributes: {attributes}"
        )
        if schema_version := raw_event.get("schema_version") != "v1":
            logger.warning(
                f"Schema version '{schema_version}' not supported. Message discarded."
            )
            return
        event_type = raw_event.get("event_type")
        current_span.set_attribute("event_type", str(event_type))
        try:
            handler = event_handlers[event_type]
        except KeyError:
            logger.warning(f"Event of type '{event_type}' unknown. Ignored.")
            current_span.add_event(
                name="wpswatch_dispatcher.discarded_transformer_event_with_invalid_type"
            )
            return
        try:
            schema = event_schemas[event_type]
        except KeyError:
            logger.warning(
                f"Event Schema for '{event_type}' not found. Message discarded."
            )
            return {}
        parsed_event = schema.parse_obj(raw_event)
        return await handler(event=parsed_event, attributes=attributes)


async def process_request(request):
    # Extract the observation and attributes from the CloudEvent
    json_data = await request.json()
    pubsub_message = json_data["message"]
    transformed_observation, attributes = extract_fields_from_message(pubsub_message)
    # Load tracing context
    tracing.pubsub_instrumentation.load_context_from_attributes(attributes)
    with tracing.tracer.start_as_current_span(
        "wpswatch_dispatcher.process_request", kind=SpanKind.CLIENT
    ) as current_span:
        timestamp = request.headers.get("ce-time") or pubsub_message.get("publish_time")
        if is_too_old(timestamp=timestamp):
            logger.warning(
                f"Message discarded (timestamp = {timestamp}). The message is too old or the retry time limit has been reached."
            )
            current_span.set_attribute("is_too_old", True)
            await send_observation_to_dead_letter_topic(
                transformed_observation, attributes
            )
            return {
                "status": "discarded",
                "reason": "Message is too old or the retry time limit has been reach",
            }
        if (version := attributes.get("gundi_version", "v1")) == "v1":
            await process_transformed_observation_v1(
                transformed_observation, attributes
            )
        elif version == "v2":
            await process_transformer_event_v2(transformed_observation, attributes)
        else:
            logger.warning(
                f"Message discarded. Version '{version}' is not supported by this dispatcher."
            )
            await send_observation_to_dead_letter_topic(
                transformed_observation, attributes
            )
            return {
                "status": "discarded",
                "reason": f"Gundi '{version}' messages are not supported",
            }
        return {"status": "processed"}
