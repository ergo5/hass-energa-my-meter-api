"""
Data updater for Energa My Meter - Smart Statistics.

Uses backward calculation from anchor (like fetch_history).
Anchor = last sum from existing statistics (if available) or meter total.
No blocking database calls - uses pre-fetched stats from Coordinator.
"""

import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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
    """Handle incremental statistics updates for Energa sensors.

    Uses backward calculation from anchor - same approach as fetch_history.
    This avoids blocking database queries during callback execution.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pre_fetched_stats: dict | None = None,
    ) -> None:
        """Initialize updater.

        Args:
            hass: Home Assistant instance
            entry: Config entry
            pre_fetched_stats: Pre-fetched statistics from Coordinator (async)
        """
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
        meter_total: float | None = None,
    ) -> tuple[list, list]:
        """Build statistics using backward calculation from anchor.

        Args:
            meter_id: Meter ID
            data_key: "import" or "export"
            hourly_data: List of {"dt": datetime, "value": float}
            entity_id: The actual entity_id for this sensor
            meter_total: Current meter total from API (anchor fallback)

        Returns:
            (energy_stats, cost_stats) lists ready for async_import_statistics
        """
        if not hourly_data:
            _LOGGER.debug("No hourly data for %s", entity_id)
            return [], []

        # Sort by datetime (newest first for backward calculation)
        sorted_data = sorted(hourly_data, key=lambda x: x["dt"], reverse=True)

        # Get anchor (starting sum)
        anchor = self._get_anchor(entity_id, meter_total, sorted_data)

        _LOGGER.debug(
            "DataUpdater for %s: anchor=%.3f, points=%d",
            entity_id,
            anchor,
            len(sorted_data),
        )

        # Get price for cost calculation
        if data_key == "import":
            price = self.entry.options.get(CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE)
        elif data_key == "import_1":
            price = self.entry.options.get(CONF_IMPORT_PRICE_1, DEFAULT_IMPORT_PRICE_1)
        elif data_key == "import_2":
            price = self.entry.options.get(CONF_IMPORT_PRICE_2, DEFAULT_IMPORT_PRICE_2)
        else:
            price = self.entry.options.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE)

        # Build statistics using backward calculation
        energy_stats = []
        running_sum = anchor

        for point in sorted_data:
            hourly_value = point.get("value") if point.get("value") is not None else 0

            # Skip invalid values (0 kWh is valid — no consumption that hour)
            if hourly_value < 0 or hourly_value > 100:
                continue

            energy_stats.append(
                {
                    "start": point["dt"],
                    "sum": running_sum,
                    "state": hourly_value,
                }
            )
            running_sum -= hourly_value

        # Sort oldest first for import
        energy_stats.sort(key=lambda x: x["start"])

        # Build cost statistics — derived from energy sum to stay synchronized.
        # cost_sum = energy_sum × price avoids anchor desynchronization.
        cost_stats = []

        for stat in energy_stats:
            hourly_energy = stat["state"] or 0
            hourly_cost = hourly_energy * price
            cost_sum = stat["sum"] * price
            cost_stats.append(
                {
                    "start": stat["start"],
                    "sum": cost_sum,
                    "state": hourly_cost,
                }
            )

        _LOGGER.info(
            "DataUpdater built %d energy stats, %d cost stats for %s",
            len(energy_stats),
            len(cost_stats),
            entity_id,
        )

        return energy_stats, cost_stats

    def _get_anchor(
        self,
        entity_id: str,
        meter_total: float | None,
        sorted_data: list[dict],
    ) -> float:
        """Get anchor sum for backward calculation.

        Priority:
        1. Meter total from API (authoritative, always correct)
        2. Pre-fetched stats last_sum (as-is, no hourly addition)
        3. Sum of all hourly values (fallback for first run)
        """
        # Priority 1: Meter total from API — most reliable anchor
        if meter_total and meter_total > 0:
            _LOGGER.debug(
                "Anchor for %s: meter_total=%.3f (from API)", entity_id, meter_total
            )
            return meter_total

        # Priority 2: Last imported sum from recorder (no hourly addition!)
        if entity_id in self._pre_fetched_stats:
            last_sum = self._pre_fetched_stats[entity_id].get("sum", 0)
            if last_sum and last_sum > 0:
                _LOGGER.debug(
                    "Anchor for %s: last_sum=%.3f (from pre-fetched stats)",
                    entity_id,
                    last_sum,
                )
                return last_sum

        # Priority 3: Fallback — sum of all hourly values (first run only)
        hourly_sum = sum(p.get("value", 0) or 0 for p in sorted_data)
        _LOGGER.debug(
            "Anchor for %s: hourly_sum=%.3f (fallback)", entity_id, hourly_sum
        )
        return hourly_sum

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
