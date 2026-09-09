"""Tests for history import anchoring in __init__.py."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.energa_mobile import _import_meter_history

WARSAW = ZoneInfo("Europe/Warsaw")


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance with recorder."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_entry():
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.options = {
        "import_price": 1.0,
        "import_price_1": 1.2,
        "import_price_2": 0.6,
        "export_price": 0.8,
        "export_price_1": 0.8,
        "export_price_2": 0.8,
    }
    return entry


@pytest.mark.asyncio
async def test_history_import_anchors_to_previous_sum_window(mock_hass, mock_entry):
    """Test that build_statistics anchors to the previous record's sum from 48h window."""
    today = datetime.now(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)
    point_dt = today - timedelta(hours=2)

    api = MagicMock()
    api.async_get_history_hourly = AsyncMock(
        return_value={
            "import": [(1.5, int(point_dt.timestamp() * 1000))],
        }
    )

    meter = {
        "meter_point_id": "360074",
        "meter_serial": "00069839",
        "zone_count": 1,
    }

    # Mock recorder
    mock_instance = MagicMock()
    prev_rec = {
        "start": point_dt - timedelta(hours=1),
        "sum": 493.675,
    }

    async def mock_async_add_executor_job(func, *args, **kwargs):
        # Handle statistics_during_period
        return {"sensor.energa_00069839_panel_energia_zuzycie": [prev_rec]}

    mock_instance.async_add_executor_job = mock_async_add_executor_job

    imported_calls = []

    def mock_async_import_statistics(hass, metadata, statistics):
        imported_calls.append((metadata, statistics))

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "homeassistant.components.recorder.get_instance",
            return_value=mock_instance,
        ),
        patch(
            "custom_components.energa_mobile.async_import_statistics",
            side_effect=mock_async_import_statistics,
        ),
        patch("homeassistant.components.persistent_notification.async_create"),
    ):
        await _import_meter_history(
            hass=mock_hass,
            api=api,
            meter=meter,
            start_date=today,
            days=1,
            entry=mock_entry,
        )

    # We should have imported energy stats and cost stats (2 calls)
    assert len(imported_calls) == 2
    energy_stats = imported_calls[0][1]
    assert len(energy_stats) == 1
    # Anchored sum: 493.675 + 1.5 = 495.175
    assert round(energy_stats[0]["sum"], 3) == 495.175
    assert energy_stats[0]["state"] == 1.5

    # Cost stats should be derived from anchored sum: 495.175 * 1.0 = 495.175
    cost_stats = imported_calls[1][1]
    assert round(cost_stats[0]["sum"], 3) == 495.175
    assert round(cost_stats[0]["state"], 3) == 1.5


@pytest.mark.asyncio
async def test_history_import_starts_at_zero_when_no_prior_stats(
    mock_hass, mock_entry
):
    """Test that build_statistics starts at 0.0 when no prior stats exist."""
    today = datetime.now(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)
    point_dt = today - timedelta(hours=2)

    api = MagicMock()
    api.async_get_history_hourly = AsyncMock(
        return_value={
            "import": [(2.0, int(point_dt.timestamp() * 1000))],
        }
    )

    meter = {
        "meter_point_id": "360074",
        "meter_serial": "00069839",
        "zone_count": 1,
    }

    mock_instance = MagicMock()

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return {}

    mock_instance.async_add_executor_job = mock_async_add_executor_job

    imported_calls = []

    def mock_async_import_statistics(hass, metadata, statistics):
        imported_calls.append((metadata, statistics))

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "homeassistant.components.recorder.get_instance",
            return_value=mock_instance,
        ),
        patch(
            "custom_components.energa_mobile.async_import_statistics",
            side_effect=mock_async_import_statistics,
        ),
        patch("homeassistant.components.persistent_notification.async_create"),
    ):
        await _import_meter_history(
            hass=mock_hass,
            api=api,
            meter=meter,
            start_date=today,
            days=1,
            entry=mock_entry,
        )

    assert len(imported_calls) == 2
    energy_stats = imported_calls[0][1]
    assert len(energy_stats) == 1
    assert energy_stats[0]["sum"] == 2.0
    assert energy_stats[0]["state"] == 2.0
