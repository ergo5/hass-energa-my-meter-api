"""Unit tests for Issue #36 (meter address matching) and Issue #35 (custom meter names)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.energa_mobile.const import DOMAIN
from custom_components.energa_mobile.sensor import (
    DeviceInfo,
    EnergaInfoSensor,
    async_setup_entry,
)
from tests.conftest import make_mock_response


class TestIssue36MeterAddressMatching:
    """Tests for fixing agreement point matching by PPE code in _fetch_all_meters."""

    @pytest.mark.asyncio
    async def test_multiple_meters_correct_address_mapping(self, api, mock_session):
        """Each meter on a multi-meter account gets its own address and contract date."""
        mock_data = {
            "response": {
                "meterPoints": [
                    {
                        "id": "mp_1",
                        "dev": "11111111",
                        "tariff": "G11",
                        "agreementPoints": [{"code": "PPE_METER_1"}],
                        "params": [],
                    },
                    {
                        "id": "mp_2",
                        "dev": "22222222",
                        "tariff": "G12W",
                        "agreementPoints": [{"code": "PPE_METER_2"}],
                        "params": [],
                    },
                ],
                # Top-level agreementPoints in reverse order to ensure matching is by code, not index
                "agreementPoints": [
                    {
                        "code": "PPE_METER_2",
                        "address": "Gdańsk, Grunwaldzka 10",
                        "dealer": {"start": 1600000000000},
                    },
                    {
                        "code": "PPE_METER_1",
                        "address": "Sopot, Monte Cassino 5",
                        "dealer": {"start": 1700000000000},
                    },
                ],
            }
        }
        resp = make_mock_response(200, mock_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()

        assert len(meters) == 2

        # Meter 1 must match PPE_METER_1 -> Sopot
        m1 = next(m for m in meters if m["meter_serial"] == "11111111")
        assert m1["ppe"] == "PPE_METER_1"
        assert m1["address"] == "Sopot, Monte Cassino 5"
        assert m1["contract_date"] == date.fromtimestamp(1700000000)

        # Meter 2 must match PPE_METER_2 -> Gdańsk
        m2 = next(m for m in meters if m["meter_serial"] == "22222222")
        assert m2["ppe"] == "PPE_METER_2"
        assert m2["address"] == "Gdańsk, Grunwaldzka 10"
        assert m2["contract_date"] == date.fromtimestamp(1600000000)

    @pytest.mark.asyncio
    async def test_agreement_points_have_no_id_field(self, api, mock_session):
        """Matching works strictly by code even when agreementPoints have no 'id' field."""
        mock_data = {
            "response": {
                "meterPoints": [
                    {
                        "id": "mp_1",
                        "dev": "33333333",
                        "tariff": "G11",
                        "agreementPoints": [{"code": "PPE_ALPHA"}],
                        "params": [],
                    }
                ],
                "agreementPoints": [
                    {
                        "code": "PPE_ALPHA",
                        "address": "Warszawa, Marszałkowska 1",
                    }
                ],
            }
        }
        resp = make_mock_response(200, mock_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()
        assert len(meters) == 1
        assert meters[0]["address"] == "Warszawa, Marszałkowska 1"

    @pytest.mark.asyncio
    async def test_single_agreement_fallback(self, api, mock_session):
        """When exactly one agreementPoint exists, it is used as an unambiguous fallback."""
        mock_data = {
            "response": {
                "meterPoints": [
                    {
                        "id": "mp_1",
                        "dev": "44444444",
                        "tariff": "G11",
                        "agreementPoints": [],  # no nested code
                        "params": [],
                    }
                ],
                "agreementPoints": [
                    {
                        "code": "PPE_SINGLE",
                        "address": "Kraków, Floriańska 2",
                    }
                ],
            }
        }
        resp = make_mock_response(200, mock_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()
        assert len(meters) == 1
        assert meters[0]["ppe"] == "PPE_SINGLE"
        assert meters[0]["address"] == "Kraków, Floriańska 2"

    @pytest.mark.asyncio
    async def test_multiple_meters_no_cross_contamination(self, api, mock_session):
        """When multiple meters and agreementPoints exist but codes do not match, no wrong address is assigned."""
        mock_data = {
            "response": {
                "meterPoints": [
                    {
                        "id": "mp_1",
                        "dev": "55555555",
                        "tariff": "G11",
                        "agreementPoints": [{"code": "PPE_UNKNOWN_1"}],
                        "params": [],
                    },
                    {
                        "id": "mp_2",
                        "dev": "66666666",
                        "tariff": "G11",
                        "agreementPoints": [{"code": "PPE_UNKNOWN_2"}],
                        "params": [],
                    },
                ],
                "agreementPoints": [
                    {
                        "code": "PPE_DIFFERENT_A",
                        "address": "Poznań, Półwiejska 1",
                    },
                    {
                        "code": "PPE_DIFFERENT_B",
                        "address": "Wrocław, Rynek 1",
                    },
                ],
            }
        }
        resp = make_mock_response(200, mock_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()
        assert len(meters) == 2
        # Neither meter should receive agreementPoints[0]
        assert meters[0]["address"] is None
        assert meters[1]["address"] is None


class TestIssue35CustomMeterName:
    """Tests for custom meter name parsing and sensor generation (Issue #35)."""

    @pytest.mark.asyncio
    async def test_custom_meter_name_parsed_from_api(self, api, mock_session):
        """mp['name'] is parsed into meter_name when different from serial."""
        mock_data = {
            "response": {
                "meterPoints": [
                    {
                        "id": "mp_custom",
                        "dev": "77777777",
                        "name": "Dom Letniskowy",
                        "tariff": "G11",
                        "agreementPoints": [{"code": "PPE_DOM"}],
                        "params": [],
                    },
                    {
                        "id": "mp_default",
                        "dev": "88888888",
                        "name": "88888888",  # name equals serial
                        "tariff": "G11",
                        "agreementPoints": [{"code": "PPE_DEFAULT"}],
                        "params": [],
                    },
                ],
                "agreementPoints": [],
            }
        }
        resp = make_mock_response(200, mock_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()
        assert len(meters) == 2

        m_custom = next(m for m in meters if m["meter_serial"] == "77777777")
        assert m_custom["meter_name"] == "Dom Letniskowy"

        m_default = next(m for m in meters if m["meter_serial"] == "88888888")
        assert m_default["meter_name"] is None

    def test_device_info_display_name(self):
        """DeviceInfo uses Energa <Custom Name> when available, else Energa <Serial>."""
        # Case 1: Custom name present
        custom_name = "Warsztat"
        serial = "99999999"
        device_name = f"Energa {custom_name}" if custom_name else f"Energa {serial}"
        info = DeviceInfo(
            identifiers={(DOMAIN, str(serial))},
            name=device_name,
            manufacturer="Energa-Operator",
        )
        assert info["name"] == "Energa Warsztat"
        assert info["identifiers"] == {(DOMAIN, "99999999")}

        # Case 2: No custom name
        custom_name = None
        device_name = f"Energa {custom_name}" if custom_name else f"Energa {serial}"
        info2 = DeviceInfo(
            identifiers={(DOMAIN, str(serial))},
            name=device_name,
            manufacturer="Energa-Operator",
        )
        assert info2["name"] == "Energa 99999999"
        assert info2["identifiers"] == {(DOMAIN, "99999999")}

    @pytest.mark.asyncio
    async def test_info_sensor_created_when_meter_name_present(self):
        """A 'Nazwa Licznika' info sensor is created when meter_name is in coordinator data."""
        added_entities = []

        def async_add_entities(entities, update_before_add=False):
            added_entities.extend(entities)

        mock_meter = {
            "meter_point_id": "mp_test",
            "meter_serial": "12345678",
            "meter_name": "Garaż",
            "ppe": "PPE_GARAZ",
            "tariff": "G11",
            "zone_count": 1,
            "address": "Gdynia, Świętojańska 1",
            "total_plus": 1000.0,
            "total_minus": None,
            "contract_date": None,
        }

        mock_api = MagicMock()
        mock_api.async_get_data = AsyncMock(return_value=[mock_meter])
        mock_api.async_get_hourly_statistics = AsyncMock(return_value={"import": [], "export": []})

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}

        hass = MagicMock()
        hass.data = {DOMAIN: {mock_entry.entry_id: {"api": mock_api}}}

        await async_setup_entry(hass, mock_entry, async_add_entities)

        info_sensors = [e for e in added_entities if isinstance(e, EnergaInfoSensor)]
        name_sensor = next((e for e in info_sensors if e._data_key == "meter_name"), None)

        assert name_sensor is not None
        assert name_sensor._attr_name == "Nazwa Licznika"
        assert name_sensor._attr_icon == "mdi:tag"

        # Verify value returns from coordinator data
        name_sensor.coordinator.data = [mock_meter]
        assert name_sensor.native_value == "Garaż"
