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

from .const import CONF_EXPORT_PRICE, CONF_IMPORT_PRICE, DOMAIN

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
            price = self.entry.options.get(CONF_IMPORT_PRICE, 1.188)
        else:
            price = self.entry.options.get(CONF_EXPORT_PRICE, 0.95)

        # Build statistics using backward calculation
        energy_stats = []
        running_sum = anchor

        for point in sorted_data:
            hourly_value = point.get("value", 0) or 0

            # Skip invalid values
            if hourly_value <= 0 or hourly_value > 100:
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

        # Build cost statistics (forward, cumulative)
        cost_stats = []
        cost_sum = self._get_cost_anchor(f"{entity_id}_cost", energy_stats, price)

        for stat in energy_stats:
            hourly_energy = stat["state"] or 0
            hourly_cost = hourly_energy * price
            cost_sum += hourly_cost
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
        1. Pre-fetched stats from Coordinator (if available)
        2. Meter total from API
        3. Sum of all hourly values (fallback)
        """
        # Try pre-fetched stats first
        if entity_id in self._pre_fetched_stats:
            last_sum = self._pre_fetched_stats[entity_id].get("sum", 0)
            if last_sum and last_sum > 0:
                # Add hourly values to continue from last point
                hourly_sum = sum(p.get("value", 0) or 0 for p in sorted_data)
                anchor = last_sum + hourly_sum
                _LOGGER.debug(
                    "Using pre-fetched anchor for %s: %.3f", entity_id, anchor
                )
                return anchor

        # Use meter total if available
        if meter_total and meter_total > 0:
            _LOGGER.debug(
                "Using meter total anchor for %s: %.3f", entity_id, meter_total
            )
            return meter_total

        # Fallback: sum of all hourly values
        hourly_sum = sum(p.get("value", 0) or 0 for p in sorted_data)
        _LOGGER.debug("Using calculated anchor for %s: %.3f", entity_id, hourly_sum)
        return hourly_sum

    def _get_cost_anchor(
        self,
        cost_entity_id: str,
        energy_stats: list[dict],
        price: float,
    ) -> float:
        """Get starting cost sum.

        If we have pre-fetched stats for cost, use those.
        Otherwise start from 0 (for initial import).
        """
        if cost_entity_id in self._pre_fetched_stats:
            last_cost = self._pre_fetched_stats[cost_entity_id].get("sum", 0)
            if last_cost and last_cost > 0:
                _LOGGER.debug(
                    "Using pre-fetched cost anchor for %s: %.3f",
                    cost_entity_id,
                    last_cost,
                )
                return last_cost

        return 0.0

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
