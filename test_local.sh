curl localhost:8181 \
  -X POST \
  -H "Content-Type: application/json" \
  -H "ce-id: 123451234512345" \
  -H "ce-specversion: 1.0" \
  -H "ce-time: 2024-08-20T18:50:15.790Z" \
  -H "ce-type: google.cloud.pubsub.topic.v1.messagePublished" \
  -H "ce-source: //pubsub.googleapis.com/projects/MY-PROJECT/topics/MY-TOPIC" \
  -d '{
      "message": {
        "data":"eyJldmVudF9pZCI6ICI0N2E0NjRhYi05OWYwLTRkMGUtOGQwYy1iNTU0YjI0NWI4YTIiLCAidGltZXN0YW1wIjogIjIwMjQtMDgtMjAgMjE6NDM6NTMuMTI5Njc5KzAwOjAwIiwgInNjaGVtYV92ZXJzaW9uIjogInYxIiwgInBheWxvYWQiOiB7ImZpbGVfcGF0aCI6ICJhdHRhY2htZW50cy9lbGVwaGFudF9hZnJpY2FfYW5pbWFsXzIxNjkzMi5qcGcifSwgImV2ZW50X3R5cGUiOiAiQXR0YWNobWVudFRyYW5zZm9ybWVkV1BTV2F0Y2gifQ==",
        "attributes":{
          "gundi_version":"v2",
          "provider_key":"gundi_trap_tagger_d88ac520-2bf6-4e6b-ab09-38ed1ec6947a",
          "gundi_id":"e6795790-4a5f-4d47-ac93-de7d7713698b",
          "related_to":"2a1e0e6c-334f-42fe-9d45-12c34ed4866f",
          "stream_type":"att",
          "source_id":"ac1b9cdc-a193-4515-b446-b177bcc5f342",
           "external_source_id":"gunditest",
           "destination_id":"79bef222-74aa-4065-88a8-ac9656246693",
           "data_provider_id":"d88ac520-2bf6-4e6b-ab09-38ed1ec6947a",
           "annotations":"{}",
           "tracing_context":"{}"
        }
      },
      "subscription": "projects/MY-PROJECT/subscriptions/MY-SUB"
    }'
# Gundi v2 Event
#  -d '{
#      "message": {
#        "data":"eyJldmVudF9pZCI6ICJiNjI5NGFjZS1kYzhjLTQ4MjAtYWQ5MC1iZTJmOTQ4YTA2ZGIiLCAidGltZXN0YW1wIjogIjIwMjQtMDgtMjAgMjE6MTA6MzIuNTY5ODk1KzAwOjAwIiwgInNjaGVtYV92ZXJzaW9uIjogInYxIiwgInBheWxvYWQiOiB7ImNhbWVyYV9pZCI6ICJndW5kaXRlc3QifSwgImV2ZW50X3R5cGUiOiAiRXZlbnRUcmFuc2Zvcm1lZFdQU1dhdGNoIn0=",
#        "attributes":{
#           "gundi_version":"v2",
#           "provider_key":"gundi_trap_tagger_d88ac520-2bf6-4e6b-ab09-38ed1ec6947a",
#           "gundi_id":"2a1e0e6c-334f-42fe-9d45-12c34ed4866f",
#           "related_to":"None",
#           "stream_type":"ev",
#           "source_id":"ac1b9cdc-a193-4515-b446-b177bcc5f342",
#           "external_source_id":"gunditest",
#           "destination_id":"79bef222-74aa-4065-88a8-ac9656246693",
#           "data_provider_id":"d88ac520-2bf6-4e6b-ab09-38ed1ec6947a",
#           "annotations":"{}",
#           "tracing_context":"{}"
#        }
#      },
#      "subscription": "projects/MY-PROJECT/subscriptions/MY-SUB"
#    }'
# Gundi v2 Attachment
#  -d '{
#      "message": {
#        "data":"eyJldmVudF9pZCI6ICI0N2E0NjRhYi05OWYwLTRkMGUtOGQwYy1iNTU0YjI0NWI4YTIiLCAidGltZXN0YW1wIjogIjIwMjQtMDgtMjAgMjE6NDM6NTMuMTI5Njc5KzAwOjAwIiwgInNjaGVtYV92ZXJzaW9uIjogInYxIiwgInBheWxvYWQiOiB7ImZpbGVfcGF0aCI6ICJhdHRhY2htZW50cy83Njg3YThkNS1hODlkLTRjZWItYmUzYi01ZTFlM2I3ZGMxYTlfZWxlcGhhbnQtZmVtYWxlLnBuZyJ9LCAiZXZlbnRfdHlwZSI6ICJBdHRhY2htZW50VHJhbnNmb3JtZWRXUFNXYXRjaCJ9",
#        "attributes":{
#          "gundi_version":"v2",
#          "provider_key":"gundi_trap_tagger_d88ac520-2bf6-4e6b-ab09-38ed1ec6947a",
#          "gundi_id":"e6795790-4a5f-4d47-ac93-de7d7713698b",
#          "related_to":"2a1e0e6c-334f-42fe-9d45-12c34ed4866f",
#          "stream_type":"att",
#          "source_id":"ac1b9cdc-a193-4515-b446-b177bcc5f342",
#           "external_source_id":"gunditest",
#           "destination_id":"79bef222-74aa-4065-88a8-ac9656246693",
#           "data_provider_id":"d88ac520-2bf6-4e6b-ab09-38ed1ec6947a",
#           "annotations":"{}",
#           "tracing_context":"{}"
#        }
#      },
#      "subscription": "projects/MY-PROJECT/subscriptions/MY-SUB"
#    }'
# Gundi v1
#  -d '{
#        "message": {
#          "data":"eyJtYW51ZmFjdHVyZXJfaWQiOiAiMDE4OTEwOTgwIiwgInNvdXJjZV90eXBlIjogInRyYWNraW5nLWRldmljZSIsICJzdWJqZWN0X25hbWUiOiAiTG9naXN0aWNzIFRydWNrIEEiLCAicmVjb3JkZWRfYXQiOiAiMjAyMy0wMy0wNyAwODo1OTowMC0wMzowMCIsICJsb2NhdGlvbiI6IHsibG9uIjogMzUuNDM5MTIsICJsYXQiOiAtMS41OTA4M30sICJhZGRpdGlvbmFsIjogeyJ2b2x0YWdlIjogIjcuNCIsICJmdWVsX2xldmVsIjogNzEsICJzcGVlZCI6ICI0MSBrcGgifX0=",
#          "attributes":{
#             "observation_type":"ps",
#             "device_id":"018910980",
#             "outbound_config_id":"1c19dc7e-73e2-4af3-93f5-a1cb322e5add",
#             "integration_id":"36485b4f-88cd-49c4-a723-0ddff1f580c4",
#             "tracing_context":"{}"
#          }
#        },
#        "subscription": "projects/MY-PROJECT/subscriptions/MY-SUB"
#      }'
# CemeraTrap
#  -d '{
#      "message": {
#        "data":"eyJmaWxlIjogImNhbWVyYXRyYXAuanBnIiwgImNhbWVyYV9uYW1lIjogIk1hcmlhbm8ncyBDYW1lcmEiLCAiY2FtZXJhX2Rlc2NyaXB0aW9uIjogInRlc3QgY2FtZXJhIiwgInRpbWUiOiAiMjAyMy0wMy0wNyAxMTo1MTowMC0wMzowMCIsICJsb2NhdGlvbiI6ICJ7XCJsb25naXR1ZGVcIjogLTEyMi41LCBcImxhdGl0dWRlXCI6IDQ4LjY1fSJ9",
#        "attributes":{
#          "observation_type":"ct",
#          "device_id":"Mariano Camera",
#          "outbound_config_id":"5f658487-67f7-43f1-8896-d78778e49c30",
#          "integration_id":"a244fddd-3f64-4298-81ed-b6fccc60cef8",
#          "tracing_context":"{}"
#        }
#      },
#      "subscription": "projects/MY-PROJECT/subscriptions/MY-SUB"
#    }'
# GeoEvent
#  -d '{
#      "message": {
#        "data":"eyJ0aXRsZSI6ICJSYWluZmFsbCIsICJldmVudF90eXBlIjogInJhaW5mYWxsX3JlcCIsICJldmVudF9kZXRhaWxzIjogeyJhbW91bnRfbW0iOiA2LCAiaGVpZ2h0X20iOiAzfSwgInRpbWUiOiAiMjAyMy0wMy0wNyAxMToyNDowMi0wNzowMCIsICJsb2NhdGlvbiI6IHsibG9uZ2l0dWRlIjogLTU1Ljc4NDk4LCAibGF0aXR1ZGUiOiAyMC44MDY3ODV9fQ==",
#        "attributes":{
#          "observation_type":"ge",
#          "device_id":"003",
#          "outbound_config_id":"9243a5e3-b16a-4dbd-ad32-197c58aeef59",
#          "integration_id":"8311c4a5-ddab-4743-b8ab-d3d57a7c8212",
#          "tracing_context":"{}"
#        }
#      },
#      "subscription": "projects/MY-PROJECT/subscriptions/MY-SUB"
#    }'
