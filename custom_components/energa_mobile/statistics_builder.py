"""Statistics builder for Energa Mobile - handles incremental sum calculation.

This module provides the StatisticsBuilder class that builds StatisticData objects
with proper incremental sums based on the last value in the database.

Pattern adopted from thedeemling/hass-energa-my-meter.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import get_last_statistics
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
TIMEZONE = ZoneInfo("Europe/Warsaw")


class StatisticsBuilder:
    """Builds StatisticData list with proper incremental sums.

    Key principle: sum = last_sum_from_db + hourly_value
    Never uses anchor/meter reading as base.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str):
        """Initialize the builder.

        Args:
            hass: Home Assistant instance for database queries
            entity_id: Entity ID to query for last statistics
        """
        self.hass = hass
        self.entity_id = entity_id

    def get_last_sum(self) -> float:
        """Get last sum from database, or 0 if none exists.

        Returns:
            Last cumulative sum value, or 0.0 if no statistics exist.
        """
        try:
            last_stats = get_last_statistics(
                self.hass, 1, self.entity_id, True, {"sum"}
            )
            if self.entity_id in last_stats and last_stats[self.entity_id]:
                result = last_stats[self.entity_id][0].get("sum", 0.0)
                _LOGGER.debug(
                    "StatisticsBuilder: last_sum for %s = %.3f", self.entity_id, result
                )
                return result
        except Exception as e:
            _LOGGER.warning(
                "StatisticsBuilder: Failed to get last sum for %s: %s",
                self.entity_id,
                e,
            )
        return 0.0

    def get_last_timestamp(self) -> datetime | None:
        """Get last imported timestamp from database.

        Returns:
            Last imported datetime, or None if no statistics exist.
        """
        try:
            last_stats = get_last_statistics(
                self.hass, 1, self.entity_id, True, {"start"}
            )
            if self.entity_id in last_stats and last_stats[self.entity_id]:
                start = last_stats[self.entity_id][0].get("start")
                if isinstance(start, (int, float)):
                    result = datetime.fromtimestamp(start, tz=TIMEZONE)
                    _LOGGER.debug(
                        "StatisticsBuilder: last_timestamp for %s = %s",
                        self.entity_id,
                        result.isoformat(),
                    )
                    return result
        except Exception as e:
            _LOGGER.warning(
                "StatisticsBuilder: Failed to get last timestamp for %s: %s",
                self.entity_id,
                e,
            )
        return None

    def build_statistics(self, hourly_data: list[dict]) -> list[StatisticData]:
        """Build StatisticData list from hourly values.

        Uses incremental sum pattern:
        1. Get last sum from database (or 0)
        2. Get last timestamp from database
        3. Filter out already-imported points
        4. Add each new point's value to running sum

        Args:
            hourly_data: List of {"dt": datetime, "value": float}, sorted oldest first

        Returns:
            List of StatisticData ready for async_import_statistics
        """
        if not hourly_data:
            _LOGGER.debug("StatisticsBuilder: No hourly data for %s", self.entity_id)
            return []

        running_sum = self.get_last_sum()
        last_ts = self.get_last_timestamp()

        _LOGGER.info(
            "StatisticsBuilder: Building stats for %s: last_sum=%.3f, last_ts=%s, input_points=%d",
            self.entity_id,
            running_sum,
            last_ts.isoformat() if last_ts else "None",
            len(hourly_data),
        )

        result = []
        skipped = 0

        for point in hourly_data:
            point_dt = point["dt"]
            point_value = point["value"]

            # Skip already imported points (critical for avoiding duplicates)
            if last_ts and point_dt <= last_ts:
                skipped += 1
                continue

            running_sum += point_value
            result.append(
                StatisticData(start=point_dt, sum=running_sum, state=point_value)
            )

        if skipped > 0:
            _LOGGER.debug(
                "StatisticsBuilder: Skipped %d already-imported points for %s",
                skipped,
                self.entity_id,
            )

        if result:
            _LOGGER.info(
                "StatisticsBuilder: Built %d new statistics for %s (final_sum=%.3f)",
                len(result),
                self.entity_id,
                running_sum,
            )
        else:
            _LOGGER.debug(
                "StatisticsBuilder: No new statistics to import for %s (all %d points already imported)",
                self.entity_id,
                len(hourly_data),
            )

        return result
