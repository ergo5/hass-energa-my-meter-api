"""
Data updater for Energa My Meter - Smart Statistics.

Forward-only calculation: adds hourly values to last known sum (or 0).
Guarantees monotonically increasing, non-negative sums.
"""

import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXPORT_PRICE,
    CONF_IMPORT_PRICE,
    CONF_IMPORT_PRICE_1,
    CONF_IMPORT_PRICE_2,
    DEFAULT_EXPORT_PRICE,
    DEFAULT_IMPORT_PRICE,
    DEFAULT_IMPORT_PRICE_1,
    DEFAULT_IMPORT_PRICE_2,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EnergaDataUpdater:
    """Handle incremental statistics updates for Energa sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pre_fetched_stats: dict | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self._pre_fetched_stats = pre_fetched_stats or {}
        self._tz = ZoneInfo("Europe/Warsaw")

    def gather_stats_for_sensor(
        self,
        meter_id: str,
        data_key: str,
        hourly_data: list[dict],
        entity_id: str,
        meter_total: float | None = None,  # kept for API compat, unused
    ) -> tuple[list, list]:
        """Build statistics for import into recorder.

        Always uses forward calculation: adds hourly values to last known sum.
        Starts from sum=0 when no existing stats are available.
        """
        if not hourly_data:
            _LOGGER.debug("No hourly data for %s", entity_id)
            return [], []

        # Get price for cost calculation
        price = self._get_price(data_key)

        # Forward calculation - from last known sum or 0
        pre_fetched = self._pre_fetched_stats.get(entity_id)

        if pre_fetched and pre_fetched.get("sum") is not None:
            energy_stats = self._forward_calculation(
                hourly_data, pre_fetched, entity_id
            )
        else:
            # First run or after stats clear - start from 0
            energy_stats = self._forward_calculation(
                hourly_data, {"sum": 0, "start": None}, entity_id
            )

        if not energy_stats:
            return [], []

        # Build cost statistics (derived from energy sum)
        cost_stats = []
        for stat in energy_stats:
            hourly_energy = stat["state"] or 0
            cost_stats.append(
                {
                    "start": stat["start"],
                    "sum": stat["sum"] * price,
                    "state": hourly_energy * price,
                }
            )

        _LOGGER.info(
            "DataUpdater built %d energy stats, %d cost stats for %s",
            len(energy_stats),
            len(cost_stats),
            entity_id,
        )

        return energy_stats, cost_stats

    def _forward_calculation(
        self, hourly_data: list[dict], pre_fetched: dict, entity_id: str
    ) -> list[dict]:
        """Forward calculation: add hourly values to last known sum.

        Guarantees monotonically increasing sums, consistent with existing stats.
        Only writes NEW points (after last known stat).
        """
        last_sum = pre_fetched.get("sum", 0)
        last_start = pre_fetched.get("start")

        # Sort oldest first
        sorted_data = sorted(hourly_data, key=lambda x: x["dt"])

        # Filter: only points AFTER last known stat
        if last_start is not None:
            if isinstance(last_start, (int, float)):
                last_dt = dt_util.utc_from_timestamp(last_start)
            else:
                last_dt = last_start
            sorted_data = [p for p in sorted_data if p["dt"] > last_dt]

        if not sorted_data:
            _LOGGER.debug(
                "Forward calc: no new points after last stat for %s", entity_id
            )
            return []

        running_sum = last_sum
        energy_stats = []

        for point in sorted_data:
            hourly_value = point.get("value") if point.get("value") is not None else 0

            if hourly_value < 0 or hourly_value > 100:
                continue

            running_sum += hourly_value
            energy_stats.append(
                {
                    "start": point["dt"],
                    "sum": running_sum,
                    "state": hourly_value,
                }
            )

        _LOGGER.debug(
            "Forward calc for %s: last_sum=%.3f, new_points=%d, final_sum=%.3f",
            entity_id,
            last_sum,
            len(energy_stats),
            running_sum,
        )

        return energy_stats

    def _get_price(self, data_key: str) -> float:
        """Get price for a given data key."""
        if data_key == "import":
            return self.entry.options.get(CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE)
        elif data_key == "import_1":
            return self.entry.options.get(CONF_IMPORT_PRICE_1, DEFAULT_IMPORT_PRICE_1)
        elif data_key == "import_2":
            return self.entry.options.get(CONF_IMPORT_PRICE_2, DEFAULT_IMPORT_PRICE_2)
        else:
            return self.entry.options.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE)

    def resolve_entity_id(self, meter_id: str, data_key: str) -> str | None:
        """Resolve entity_id from entity registry.

        Returns the actual HA entity_id for Panel Energia sensors.
        """
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(self.hass)

        # Look for our sensor with the stats suffix
        unique_id_pattern = f"energa_{meter_id}_{data_key}_stats"

        for entity in registry.entities.values():
            if entity.unique_id == unique_id_pattern and entity.platform == DOMAIN:
                return entity.entity_id

        return None
