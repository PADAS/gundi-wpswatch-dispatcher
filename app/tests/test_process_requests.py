import pytest
from app.core import settings
from smartconnect import SMARTClientException
from fastapi.testclient import TestClient

from app.core.errors import TooManyRequests
from app.main import app

api_client = TestClient(app)

# ToDo: Add tests for cameratrap events
