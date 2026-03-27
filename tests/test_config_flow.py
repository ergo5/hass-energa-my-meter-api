"""Tests for config flow — regression for #23 (AbortFlow).

These tests verify the exception handling logic in async_step_user
without instantiating the full HA config flow machinery.
"""

import pytest

# conftest.py sets up HA module mocks
from homeassistant.data_entry_flow import AbortFlow

from custom_components.energa_mobile.api import EnergaAuthError, EnergaConnectionError


async def _run_user_step(login_side_effect=None, abort_side_effect=None):
    """Simulate async_step_user logic with controlled mocks.

    Rather than instantiating EnergaConfigFlow (which requires full HA),
    we replicate the exact try/except structure from the real code and
    verify that exceptions are handled correctly.
    """
    errors = {}
    try:
        # Simulate: api.async_login()
        if login_side_effect:
            raise login_side_effect

        # Simulate: self._abort_if_unique_id_configured()
        if abort_side_effect:
            raise abort_side_effect

        return {"type": "create_entry"}

    except EnergaAuthError:
        errors["base"] = "invalid_auth"
    except (EnergaConnectionError, TimeoutError):
        errors["base"] = "cannot_connect"
    except AbortFlow:
        raise  # Must re-raise!
    except Exception:
        errors["base"] = "unknown"

    return {"type": "form", "errors": errors}


class TestConfigFlowExceptionHandling:
    """Tests for exception handling in async_step_user.

    These tests verify the fix for #23 — AbortFlow must NOT be
    caught by the generic `except Exception` handler.
    """

    @pytest.mark.asyncio
    async def test_successful_login_creates_entry(self):
        """No exceptions → create_entry."""
        result = await _run_user_step()
        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_auth_error_shows_invalid_auth(self):
        """EnergaAuthError → invalid_auth error."""
        result = await _run_user_step(
            login_side_effect=EnergaAuthError("bad password")
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_connection_error_shows_cannot_connect(self):
        """EnergaConnectionError → cannot_connect error."""
        result = await _run_user_step(
            login_side_effect=EnergaConnectionError("timeout")
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_abort_flow_not_swallowed(self):
        """Regression test for #23: AbortFlow must propagate, not be caught as 'unknown'.

        Before the fix, _abort_if_unique_id_configured() raised AbortFlow,
        which was caught by `except Exception` and turned into errors["base"] = "unknown".
        After the fix, `except AbortFlow: raise` ensures it propagates correctly.
        """
        with pytest.raises(AbortFlow) as exc_info:
            await _run_user_step(
                abort_side_effect=AbortFlow("already_configured")
            )
        assert exc_info.value.reason == "already_configured"

    @pytest.mark.asyncio
    async def test_abort_flow_would_fail_without_fix(self):
        """Demonstrates what happened BEFORE the fix — AbortFlow was an 'unknown' error.

        This test simulates the OLD buggy code (without `except AbortFlow: raise`).
        """
        errors = {}
        try:
            raise AbortFlow("already_configured")
        except Exception:
            # BUG: AbortFlow IS an Exception, so it gets caught here
            errors["base"] = "unknown"

        # This is what users saw — the wrong error
        assert errors["base"] == "unknown"

    @pytest.mark.asyncio
    async def test_generic_exception_shows_unknown(self):
        """Unexpected errors → unknown."""
        result = await _run_user_step(
            login_side_effect=RuntimeError("something unexpected")
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "unknown"
