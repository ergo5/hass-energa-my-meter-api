import sys
from unittest.mock import MagicMock, AsyncMock
import types
import asyncio
from datetime import datetime

# ==========================================
# 1. MOCK HOME ASSISTANT ENVIRONMENT
# ==========================================
# We need to mock all HA modules BEFORE importing the integration code
# because the user likely doesn't have 'homeassistant' package installed here.

mock_ha = types.ModuleType("homeassistant")
mock_ha.core = types.ModuleType("homeassistant.core")
mock_ha.config_entries = types.ModuleType("homeassistant.config_entries")
mock_ha.helpers = types.ModuleType("homeassistant.helpers")
mock_ha.helpers.aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
mock_ha.helpers.entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
mock_ha.exceptions = types.ModuleType("homeassistant.exceptions")
mock_ha.components = types.ModuleType("homeassistant.components")
mock_ha.components.recorder = types.ModuleType("homeassistant.components.recorder")
mock_ha.components.recorder.statistics = types.ModuleType("homeassistant.components.recorder.statistics")
mock_ha.components.recorder.models = types.ModuleType("homeassistant.components.recorder.models")

# Mock Classes/Objects
mock_ha.core.HomeAssistant = MagicMock()
mock_ha.core.ServiceCall = MagicMock()
mock_ha.config_entries.ConfigEntry = MagicMock()
mock_ha.components.recorder.models.StatisticData = MagicMock()
mock_ha.components.recorder.models.StatisticMetaData = MagicMock()
mock_ha.components.recorder.statistics.async_import_statistics = MagicMock()
mock_ha.exceptions.ConfigEntryAuthFailed = Exception
mock_ha.exceptions.ConfigEntryNotReady = Exception

# Fix imports for functionality
mock_ha.helpers.aiohttp_client.async_get_clientsession = MagicMock()
mock_ha.helpers.entity_registry.async_get = MagicMock()

# Add to sys.modules
sys.modules["homeassistant"] = mock_ha
sys.modules["homeassistant.core"] = mock_ha.core
sys.modules["homeassistant.config_entries"] = mock_ha.config_entries
sys.modules["homeassistant.helpers"] = mock_ha.helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = mock_ha.helpers.aiohttp_client
sys.modules["homeassistant.helpers.entity_registry"] = mock_ha.helpers.entity_registry
sys.modules["homeassistant.exceptions"] = mock_ha.exceptions
sys.modules["homeassistant.components"] = mock_ha.components
sys.modules["homeassistant.components.recorder"] = mock_ha.components.recorder
sys.modules["homeassistant.components.recorder.statistics"] = mock_ha.components.recorder.statistics
sys.modules["homeassistant.components.recorder.models"] = mock_ha.components.recorder.models

# Also mock voluptuous
sys.modules["voluptuous"] = MagicMock()

# Robust ZoneInfo Mock
from datetime import tzinfo, timedelta
class MockZoneInfo(tzinfo):
    def __init__(self, key): self.key = key
    def utcoffset(self, dt): return timedelta(hours=1)
    def dst(self, dt): return timedelta(0)
    def tzname(self, dt): return self.key

mock_zoneinfo_mod = types.ModuleType("zoneinfo")
mock_zoneinfo_mod.ZoneInfo = MockZoneInfo
sys.modules["zoneinfo"] = mock_zoneinfo_mod

# ==========================================
# 2. IMPORT CODE UNDER TEST
# ==========================================
# Access local components path
import os
sys.path.append(os.path.join(os.getcwd(), "custom_components"))

# Now we can safely import the integration modules
# We need to bypass relative imports if running from root, but since we appended custom_components
# we might need to adjust how we import. 
# Best way: imitate package structure or just import the file content?
# Let's rely on Python resolving 'energa_mobile' if we are in root and 'custom_components' is there.
# Actually, relative imports like 'from .api' fail if not run as package.
# We will mock the local deps too for simplicity of unit testing just the Logic.

# Mocking .api and .const to avoid strict dep issues and focus on __init__ logic
mock_api_mod = types.ModuleType("custom_components.energa_mobile.api")
mock_api_mod.EnergaAPI = MagicMock()
mock_api_mod.EnergaAuthError = Exception
mock_api_mod.EnergaConnectionError = Exception
mock_api_mod.EnergaTokenExpiredError = Exception

mock_const_mod = types.ModuleType("custom_components.energa_mobile.const")
mock_const_mod.DOMAIN = "energa_mobile"
mock_const_mod.CONF_USERNAME = "user"
mock_const_mod.CONF_PASSWORD = "pass"

sys.modules["custom_components.energa_mobile.api"] = mock_api_mod
sys.modules["custom_components.energa_mobile.const"] = mock_const_mod

# Now we import the FUNCTION itself specifically from the file path to allow relative imports to partial work 
# or just patch around it.
# Easier hack: Read file and exec it in a namespace where we control imports.

import importlib.util
spec = importlib.util.spec_from_file_location("energa_init", "custom_components/energa_mobile/__init__.py")
energa_init = importlib.util.module_from_spec(spec)

# We need to make sure the relative imports in __init__.py work or are mocked.
# "from .api import ..." -> This expects __package__ to be set.
energa_init.__package__ = "custom_components.energa_mobile"
sys.modules["custom_components.energa_mobile"] = energa_init # Register package

# EXECUTE IMPORT
spec.loader.exec_module(energa_init)

# ==========================================
# 3. DEFINE TEST CASE
# ==========================================

async def test_run_history_import_fix():
    print(">>> Starting Simulation Test for Data Spike Fix <<<")

    # A. Setup Mock HASS
    hass = MagicMock()
    # Mock Entity Registry
    mock_er = MagicMock()
    mock_er.async_get_entity_id.side_effect = lambda domain, platform, uid: f"sensor.{uid}"
    
    # Mock helpers.entity_registry.async_get(hass) -> mock_er
    mock_ha.helpers.entity_registry.async_get = MagicMock(return_value=mock_er)
    
    # Mock states.async_set - THIS IS WHAT WE WANT TO ENSURE IS NOT CALLED
    hass.states.async_set = MagicMock()
    hass.async_create_task = MagicMock()

    # B. Setup Mock API
    api = AsyncMock()
    # Mock returns: 2 hourly data points
    # api.async_get_history_hourly.return_value = {"import": [1.0, 2.0], "export": [0.5, 0.5]}
    # Correct structure from code: {"import": [], "export": []}
    api.async_get_history_hourly.return_value = {
        "import": [1.0, 1.0], # 2 kWh total import for that day
        "export": [0.5, 0.5]  # 1 kWh total export for that day
    }

    # C. Run the function
    meter_id = "12345"
    start_date = datetime(2024, 1, 1)
    days = 1
    
    print(f"   Simulating history import for {days} day(s)...")
    await energa_init.run_history_import(hass, api, meter_id, start_date, days)

    # D. ASSERTIONS
    print("\n>>> Verification Results <<<")
    
    # 1. Verify Statistics IMPORT happened
    # We expect async_import_statistics to be called
    import_stats_call = mock_ha.components.recorder.statistics.async_import_statistics
    if import_stats_call.called:
        print("✅ [PASS] Statistics were imported (async_import_statistics called).")
        # Optional: check count (should be twice per day loop: one for import, one for export)
        print(f"         Call count: {import_stats_call.call_count}")
    else:
        print("❌ [FAIL] Statistics were NOT imported!")

    # 2. Verify Live State Update prevented
    # We expect hass.states.async_set to NOT be called
    if hass.states.async_set.called:
        print("❌ [FAIL] Live Entity State was UPDATED! Fix failed!")
        print("         Called with:", hass.states.async_set.call_args)
    else:
        print("✅ [PASS] Live Entity State was NOT updated (hass.states.async_set NOT called).")
        print("         The data spike issue is fixed.")

# Run the async test
asyncio.run(test_run_history_import_fix())
