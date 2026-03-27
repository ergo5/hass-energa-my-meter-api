"""Tests for EnergaAPI — login, retry, token refresh."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.energa_mobile.api import (
    EnergaAuthError,
    EnergaConnectionError,
    EnergaTokenExpiredError,
)
from tests.conftest import make_mock_response


class TestAsyncLogin:
    """Tests for EnergaAPI.async_login()."""

    @pytest.mark.asyncio
    async def test_login_success(self, api, mock_session):
        """Login succeeds when API returns success=True."""
        # Session init call
        session_resp = make_mock_response(200, {})
        # Login call
        login_resp = make_mock_response(200, {"success": True, "token": "tok123"})

        mock_session.get = MagicMock(side_effect=[session_resp, login_resp])

        result = await api.async_login()

        assert result is True
        assert api._token == "tok123"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, api, mock_session):
        """Login raises EnergaAuthError on invalid credentials."""
        session_resp = make_mock_response(200, {})
        login_resp = make_mock_response(200, {"success": False, "error": "error.login.password"})

        mock_session.get = MagicMock(side_effect=[session_resp, login_resp])

        with pytest.raises(EnergaAuthError):
            await api.async_login()

    @pytest.mark.asyncio
    async def test_login_http_error(self, api, mock_session):
        """Login raises EnergaConnectionError on HTTP error."""
        session_resp = make_mock_response(200, {})
        # Override: don't raise on resp.json, raise on status check to match code logic
        inner_resp = AsyncMock()
        inner_resp.status = 500
        login_ctx = AsyncMock()
        login_ctx.__aenter__ = AsyncMock(return_value=inner_resp)
        login_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session.get = MagicMock(side_effect=[session_resp, login_ctx])

        with pytest.raises(EnergaConnectionError):
            await api.async_login()

    @pytest.mark.asyncio
    async def test_login_clears_cookies(self, api, mock_session):
        """Login clears cookies and token before re-login."""
        api._token = "old_token"

        session_resp = make_mock_response(200, {})
        login_resp = make_mock_response(200, {"success": True, "token": "new_token"})
        mock_session.get = MagicMock(side_effect=[session_resp, login_resp])

        await api.async_login()

        mock_session.cookie_jar.clear.assert_called_once()
        assert api._token == "new_token"

    @pytest.mark.asyncio
    async def test_login_without_token_in_response(self, api, mock_session):
        """Login works even if server doesn't return a token (session-only auth)."""
        session_resp = make_mock_response(200, {})
        login_resp = make_mock_response(200, {"success": True})

        mock_session.get = MagicMock(side_effect=[session_resp, login_resp])

        result = await api.async_login()

        assert result is True
        assert api._token is None  # No token, but login still succeeded


class TestApiGetRetry:
    """Tests for _api_get retry logic — regression for #25."""

    @pytest.mark.asyncio
    async def test_403_triggers_relogin_and_uses_fresh_token(self, api, mock_session):
        """Regression test for #25: after 403, retry must use the NEW token."""
        api._token = "old_token"

        # First call: 403
        resp_403 = make_mock_response(403, {})
        # Login calls (session init + login)
        login_session = make_mock_response(200, {})
        login_resp = make_mock_response(200, {"success": True, "token": "fresh_token"})
        # Second call: 200 with data
        resp_200 = make_mock_response(200, {"response": {"data": "ok"}})

        mock_session.get = MagicMock(
            side_effect=[resp_403, login_session, login_resp, resp_200]
        )

        result = await api._api_get("/resources/user/data")

        assert result == {"response": {"data": "ok"}}
        # Verify the retried request used fresh_token, not old_token
        # The 4th call (resp_200) should have token=fresh_token in params
        final_call = mock_session.get.call_args_list[-1]
        final_params = final_call[1].get("params", {}) if final_call[1] else {}
        assert final_params.get("token") == "fresh_token"

    @pytest.mark.asyncio
    async def test_double_403_raises_token_expired(self, api, mock_session):
        """Two consecutive 403s should raise EnergaTokenExpiredError."""
        api._token = "bad_token"

        # First 403
        resp_403_1 = make_mock_response(403, {})
        # Re-login
        login_session = make_mock_response(200, {})
        login_resp = make_mock_response(200, {"success": True, "token": "still_bad"})
        # Second 403
        resp_403_2 = make_mock_response(403, {})

        mock_session.get = MagicMock(
            side_effect=[resp_403_1, login_session, login_resp, resp_403_2]
        )

        with pytest.raises(EnergaTokenExpiredError):
            await api._api_get("/resources/user/data")

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self, api, mock_session):
        """Normal 200 response requires no retry."""
        api._token = "valid_token"
        resp = make_mock_response(200, {"response": {"ok": True}})
        mock_session.get = MagicMock(return_value=resp)

        result = await api._api_get("/resources/user/data")

        assert result == {"response": {"ok": True}}
        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_closed_session_recovery(self, api, mock_session):
        """Closed session triggers new session creation and re-login."""
        mock_session.closed = True

        new_session = MagicMock(spec=aiohttp.ClientSession)
        new_session.closed = False
        new_session.cookie_jar = MagicMock()
        new_session.cookie_jar.__len__ = lambda self: 1

        # After session creation: login calls + actual request
        login_session = make_mock_response(200, {})
        login_resp = make_mock_response(200, {"success": True, "token": "new_tok"})
        data_resp = make_mock_response(200, {"response": "data"})
        new_session.get = MagicMock(
            side_effect=[login_session, login_resp, data_resp]
        )

        api._create_session_fn = lambda: new_session

        result = await api._api_get("/resources/user/data")

        assert result == {"response": "data"}
        assert api._session is new_session
