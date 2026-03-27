"""Shared fixtures for Energa integration tests."""

import sys
from unittest.mock import MagicMock

# Mock homeassistant modules so we can import integration code
# without installing the full homeassistant package
_HA_MODULES = [
    "homeassistant",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.selector",
    "homeassistant.helpers.entity_registry",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.frame",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.recorder",
    "homeassistant.components.recorder.models",
    "homeassistant.components.recorder.models.statistics",
    "homeassistant.components.recorder.statistics",
    "homeassistant.components.persistent_notification",
    "homeassistant.const",
    "homeassistant.util",
    "homeassistant.util.dt",
    "homeassistant.exceptions",
]

for mod_name in _HA_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Ensure AbortFlow is a real exception class (needed for pytest.raises)
class _AbortFlow(Exception):
    def __init__(self, reason=""):
        self.reason = reason
        super().__init__(reason)

sys.modules["homeassistant.data_entry_flow"].AbortFlow = _AbortFlow

# Ensure config_entries has the FlowResult type
sys.modules["homeassistant"].config_entries = sys.modules["homeassistant.config_entries"]

# Provide SensorDeviceClass, SensorStateClass, SensorEntity as mock enums
sensor_mod = sys.modules["homeassistant.components.sensor"]
sensor_mod.SensorDeviceClass = MagicMock()
sensor_mod.SensorStateClass = MagicMock()
sensor_mod.SensorEntity = type("SensorEntity", (), {})

# Now safe to import
import pytest
from unittest.mock import AsyncMock
import aiohttp

from custom_components.energa_mobile.api import EnergaAPI


@pytest.fixture
def mock_session():
    """Create a mock aiohttp.ClientSession."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.cookie_jar = MagicMock()
    session.cookie_jar.__len__ = lambda self: 3
    return session


@pytest.fixture
def api(mock_session):
    """Create an EnergaAPI instance with mocked session."""
    return EnergaAPI(
        username="test@example.com",
        password="testpass",
        device_token="abc123",
        session=mock_session,
    )


@pytest.fixture
def g11_user_data():
    """Sample API response for a single-zone G11 meter."""
    return {
        "success": True,
        "response": {
            "meterPoints": [
                {
                    "id": 123456,
                    "dev": "30132815",
                    "tariff": "G11",
                    "name": "30132815",
                    "lastMeasurements": [
                        {"zone": "A+", "value": 26955.924, "unit": ""},
                        {"zone": "A-", "value": 27048.755, "unit": ""},
                    ],
                    "meterObjects": [
                        {"obis": "1-0:1.8.0*255", "name": None},
                        {"obis": "1-0:2.8.0*255", "name": None},
                    ],
                    "agreementPoints": [{"code": "590243835014852258"}],
                }
            ],
            "agreementPoints": [
                {
                    "code": "590243835014852258",
                    "address": "83-330 Maśkowo, Pałacowa 98",
                }
            ],
            "activationDate": "2025-06-11",
        },
    }


@pytest.fixture
def g12w_user_data():
    """Sample API response for a multi-zone G12W meter."""
    return {
        "success": True,
        "response": {
            "meterPoints": [
                {
                    "id": 360074,
                    "dev": "00069839",
                    "tariff": "G12W",
                    "name": "00069839",
                    "lastMeasurements": [
                        {"zone": "A+ strefa 1", "value": 19279.234, "unit": ""},
                        {"zone": "A+ strefa 2", "value": 26170.309, "unit": ""},
                        {"zone": "A- strefa 1", "value": 15579.564, "unit": ""},
                        {"zone": "A- strefa 2", "value": 13947.306, "unit": ""},
                    ],
                    "meterObjects": [
                        {"obis": "1-0:1.8.1*255", "name": None},
                        {"obis": "1-0:1.8.2*255", "name": None},
                        {"obis": "1-0:2.8.1*255", "name": None},
                        {"obis": "1-0:2.8.2*255", "name": None},
                    ],
                    "agreementPoints": [{"code": "590243891023106980"}],
                }
            ],
            "agreementPoints": [
                {
                    "code": "590243891023106980",
                    "address": "87-148 Łysomice, Wiśniowa 9",
                }
            ],
            "activationDate": "2026-03-15",
        },
    }


def make_mock_response(status=200, json_data=None):
    """Create a mock aiohttp response with __aenter__/__aexit__."""
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    response.raise_for_status = MagicMock()
    if status >= 400:
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=status
        )

    # Context manager support
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx
