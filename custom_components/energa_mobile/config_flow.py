"""Config flow for Energa My Meter integration."""

import logging
import secrets
from datetime import datetime

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EnergaAPI, EnergaAuthError, EnergaConnectionError
from .const import (
    CONF_DEVICE_TOKEN,
    CONF_EXPORT_PRICE,
    CONF_IMPORT_PRICE,
    CONF_IMPORT_PRICE_1,
    CONF_IMPORT_PRICE_2,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_EXPORT_PRICE,
    DEFAULT_IMPORT_PRICE,
    DEFAULT_IMPORT_PRICE_1,
    DEFAULT_IMPORT_PRICE_2,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EnergaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Energa My Meter."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow handler."""
        return EnergaOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle initial user setup."""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            # Generate unique device token for this installation
            device_token = secrets.token_hex(32)
            api = EnergaAPI(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                device_token,
                session,
            )
            try:
                await api.async_login()
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                # Store device token along with credentials
                entry_data = {
                    **user_input,
                    CONF_DEVICE_TOKEN: device_token,
                }
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=entry_data,
                )
            except EnergaAuthError:
                errors["base"] = "invalid_auth"
            except (EnergaConnectionError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Handle reauth when credentials expire."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth confirmation."""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            username = self.reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            # Preserve existing device token or generate new one
            device_token = self.reauth_entry.data.get(
                CONF_DEVICE_TOKEN
            ) or secrets.token_hex(32)
            api = EnergaAPI(username, password, device_token, session)
            try:
                await api.async_login()
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_DEVICE_TOKEN: device_token,
                    },
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except EnergaAuthError:
                errors["base"] = "invalid_auth"
            except (EnergaConnectionError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={
                "username": self.reauth_entry.data[CONF_USERNAME]
            },
            errors=errors,
        )


class EnergaOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Energa My Meter."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Show options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["credentials", "prices", "history", "clear_stats"],
        )

    async def async_step_credentials(self, user_input=None):
        """Handle credential update."""
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            # Preserve existing device token or generate new one
            device_token = self._config_entry.data.get(
                CONF_DEVICE_TOKEN
            ) or secrets.token_hex(32)
            api = EnergaAPI(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                device_token,
                session,
            )
            try:
                await api.async_login()
                # Preserve device token in updated entry data
                entry_data = {
                    **user_input,
                    CONF_DEVICE_TOKEN: device_token,
                }
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=entry_data,
                )
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            except EnergaAuthError:
                errors["base"] = "invalid_auth"
            except (EnergaConnectionError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during credential update")
                errors["base"] = "unknown"

        current_user = self._config_entry.data.get(CONF_USERNAME)
        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=current_user): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    def _has_multi_zone_meters(self) -> bool:
        """Check if any meter uses multi-zone tariff (G12w)."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(
            self._config_entry.entry_id, {}
        )
        api = entry_data.get("api") if isinstance(entry_data, dict) else None
        if api and hasattr(api, "has_multi_zone_meters"):
            return api.has_multi_zone_meters()
        return False

    async def async_step_prices(self, user_input=None):
        """Handle energy price configuration."""
        if user_input is not None:
            # Store prices in options
            new_options = {**self._config_entry.options, **user_input}
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                options=new_options,
            )
            # Reload integration to apply new prices
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        has_zones = self._has_multi_zone_meters()

        # Get current values from options
        current_export = self._config_entry.options.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE)

        if has_zones:
            # G12w: show zone-specific prices
            current_price_1 = self._config_entry.options.get(CONF_IMPORT_PRICE_1, DEFAULT_IMPORT_PRICE_1)
            current_price_2 = self._config_entry.options.get(CONF_IMPORT_PRICE_2, DEFAULT_IMPORT_PRICE_2)

            return self.async_show_form(
                step_id="prices",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_IMPORT_PRICE_1, default=current_price_1
                        ): vol.Coerce(float),
                        vol.Required(
                            CONF_IMPORT_PRICE_2, default=current_price_2
                        ): vol.Coerce(float),
                        vol.Required(
                            CONF_EXPORT_PRICE, default=current_export
                        ): vol.Coerce(float),
                    }
                ),
            )
        else:
            # Single-zone: show single import price
            current_import = self._config_entry.options.get(CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE)

            return self.async_show_form(
                step_id="prices",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_IMPORT_PRICE, default=current_import
                        ): vol.Coerce(float),
                        vol.Required(
                            CONF_EXPORT_PRICE, default=current_export
                        ): vol.Coerce(float),
                    }
                ),
            )

    async def async_step_history(self, user_input=None):
        """Handle history import from options."""
        from . import _import_meter_history

        entry_data = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {})
        api = entry_data.get("api") if isinstance(entry_data, dict) else entry_data
        if not api:
            return self.async_abort(reason="integration_not_ready")

        # Get contract date hint
        contract_str = "Nieznana"
        default_date = None
        if api._meters_data:
            first_meter = api._meters_data[0]
            if first_meter.get("contract_date"):
                contract_str = str(first_meter["contract_date"])
                default_date = str(first_meter["contract_date"])

        if user_input is not None:
            start_date = datetime.strptime(user_input["start_date"], "%Y-%m-%d")
            days = (datetime.now() - start_date).days
            if days < 1:
                days = 1

            # Get active meters - handle token expiry
            try:
                meters = await api.async_get_data()
            except Exception as err:
                # Token expired or other API error - try to re-login
                from .api import EnergaAuthError, EnergaTokenExpiredError

                if isinstance(err, (EnergaTokenExpiredError, EnergaAuthError)):
                    try:
                        await api.async_login()
                        meters = await api.async_get_data()
                    except Exception as login_err:
                        return self.async_abort(
                            reason="cannot_connect",
                            description_placeholders={"error": str(login_err)},
                        )
                else:
                    return self.async_abort(
                        reason="cannot_connect",
                        description_placeholders={"error": str(err)},
                    )

            active_meters = [
                m
                for m in meters
                if m.get("total_plus") and float(m.get("total_plus", 0)) > 0
            ]

            # FIX: Pass full meter dict, not just ID
            for meter in active_meters:
                self.hass.async_create_task(
                    _import_meter_history(
                        self.hass, api, meter, start_date, days, self._config_entry
                    )
                )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="history",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "start_date", default=default_date
                    ): selector.DateSelector(),
                }
            ),
            description_placeholders={"contract_date": contract_str},
        )

    async def async_step_clear_stats(self, user_input=None):
        """Clear Energy Panel statistics for Energa sensors.

        This removes all historical statistics from Home Assistant's recorder
        for Energa energy/production sensors. Use this if:
        - Statistics show incorrect spikes or anomalies
        - After updating the integration to fix data format issues

        Note: After clearing, use 'Pobierz Historię' to reimport clean data.
        """
        from homeassistant.components import recorder
        from homeassistant.helpers import entity_registry as er

        if user_input is not None:
            rec = recorder.get_instance(self.hass)
            entity_registry = er.async_get(self.hass)

            # Find all Energa Panel Energia sensors (energy statistics only)
            # These have "panel_energia_zuzycie" or "panel_energia_produkcja" in entity_id
            # and "_stats" marker in unique_id (identifies Panel Energia sensors)
            statistic_ids = [
                entity.entity_id
                for entity in entity_registry.entities.values()
                if entity.platform == DOMAIN
                and (
                    "panel_energia_zuzycie" in entity.entity_id
                    or "panel_energia_produkcja" in entity.entity_id
                    or "panel_energia_strefa" in entity.entity_id
                )
            ]

            if statistic_ids:
                cost_statistic_ids = [f"{sid}_cost" for sid in statistic_ids]
                all_statistic_ids = statistic_ids + cost_statistic_ids
                rec.async_clear_statistics(all_statistic_ids)
                _LOGGER.info(
                    "Cleared Energy Panel statistics for %d Energa sensors: %s",
                    len(statistic_ids),
                    all_statistic_ids,
                )
            else:
                _LOGGER.warning("No Energa Panel Energia sensors found to clear")

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="clear_stats",
            description_placeholders={
                "warning": "⚠️ To **nieodwracalnie wyczyści** wszystkie statystyki energii i kosztów dla Panelu Energia.\n\nPo wyczyszczeniu użyj 'Pobierz Historię' aby ponownie zaimportować dane."
            },
        )
