"""Tests for API zone detection and meter parsing."""

from unittest.mock import MagicMock

import pytest

from custom_components.energa_mobile.api import EnergaConnectionError
from tests.conftest import make_mock_response


class TestFetchAllMeters:
    """Tests for _fetch_all_meters — G11 vs G12W detection."""

    @pytest.mark.asyncio
    async def test_g11_single_zone(self, api, mock_session, g11_user_data):
        """G11 meter has zone_count=1, single A+/A- totals."""
        resp = make_mock_response(200, g11_user_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()

        assert len(meters) == 1
        m = meters[0]
        assert m["meter_serial"] == "30132815"
        assert m["tariff"] == "G11"
        assert m["zone_count"] == 1
        assert m["total_plus"] == 26955.924
        assert m["total_minus"] == 27048.755
        assert m["total_plus_1"] is None  # No zone split
        assert m["total_plus_2"] is None

    @pytest.mark.asyncio
    async def test_g12w_multi_zone(self, api, mock_session, g12w_user_data):
        """G12W meter has zone_count=2 with per-zone totals."""
        resp = make_mock_response(200, g12w_user_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()

        assert len(meters) == 1
        m = meters[0]
        assert m["meter_serial"] == "00069839"
        assert m["tariff"] == "G12W"
        assert m["zone_count"] == 2
        assert m["total_plus_1"] == 19279.234
        assert m["total_plus_2"] == 26170.309
        assert m["total_minus_1"] == 15579.564
        assert m["total_minus_2"] == 13947.306
        # Total = sum of both zones
        assert m["total_plus"] == pytest.approx(19279.234 + 26170.309)
        assert m["total_minus"] == pytest.approx(15579.564 + 13947.306)

    @pytest.mark.asyncio
    async def test_ppe_from_nested_agreement(self, api, mock_session, g11_user_data):
        """PPE is extracted from nested agreementPoints."""
        resp = make_mock_response(200, g11_user_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()

        assert meters[0]["ppe"] == "590243835014852258"

    @pytest.mark.asyncio
    async def test_empty_response_raises(self, api, mock_session):
        """Empty API response raises EnergaConnectionError."""
        resp = make_mock_response(200, {"response": None})
        mock_session.get = MagicMock(return_value=resp)

        with pytest.raises(EnergaConnectionError):
            await api._fetch_all_meters()

    @pytest.mark.asyncio
    async def test_obis_detection(self, api, mock_session, g11_user_data):
        """OBIS codes for import (1.8.0) and export (2.8.0) are detected."""
        resp = make_mock_response(200, g11_user_data)
        mock_session.get = MagicMock(return_value=resp)

        meters = await api._fetch_all_meters()

        m = meters[0]
        assert m["obis_plus"] == "1-0:1.8.0*255"
        assert m["obis_minus"] == "1-0:2.8.0*255"


class TestHasMultiZoneMeters:
    """Tests for has_multi_zone_meters() convenience check."""

    def test_single_zone_returns_false(self, api):
        """G11 meter → False."""
        api._meters_data = [{"zone_count": 1}]
        assert api.has_multi_zone_meters() is False

    def test_multi_zone_returns_true(self, api):
        """G12W meter → True."""
        api._meters_data = [{"zone_count": 2}]
        assert api.has_multi_zone_meters() is True

    def test_mixed_meters(self, api):
        """One G11 + one G12W → True (any multi)."""
        api._meters_data = [{"zone_count": 1}, {"zone_count": 2}]
        assert api.has_multi_zone_meters() is True

    def test_empty_meters(self, api):
        """No meters → False."""
        api._meters_data = []
        assert api.has_multi_zone_meters() is False
