"""Tests for DST handling in hourly statistics (issue #26).

Validates that the datetime constructor approach produces correct
timestamps for all scenarios. Key finding: Python's ZoneInfo correctly
normalizes .replace() results, so the constructor is functionally
equivalent but more explicit and readable.

The real DST issue is the duplicate UTC timestamp on spring-forward days:
- hour 2 (02:00+01:00 CET) and hour 3 (03:00+02:00 CEST) both map to
  01:00 UTC. This causes async_import_statistics to receive two data
  points with the same start time.
"""

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
UTC = ZoneInfo("UTC")

SPRING_FWD_DATE = datetime(2026, 3, 29).date()
WINTER_DATE = datetime(2026, 1, 15).date()
SUMMER_DATE = datetime(2026, 6, 15).date()
FALL_BACK_DATE = datetime(2026, 10, 25).date()


def map_hour(day_date, hour_idx: int) -> datetime:
    """Current hour mapping: datetime constructor with ZoneInfo."""
    tz = ZoneInfo("Europe/Warsaw")
    return datetime(
        day_date.year, day_date.month, day_date.day,
        hour_idx, 0, 0, tzinfo=tz,
    )


def midnight_ts(day_date) -> int:
    """Current midnight timestamp construction."""
    tz = ZoneInfo("Europe/Warsaw")
    return int(
        datetime(day_date.year, day_date.month, day_date.day,
                 0, 0, 0, tzinfo=tz).timestamp() * 1000
    )


class TestMidnightTimestamp(unittest.TestCase):
    """Test API request timestamp construction."""

    def test_march29_midnight_is_cet(self):
        """March 29 midnight is CET (+01:00), not CEST."""
        dt = datetime(2026, 3, 29, 0, 0, 0, tzinfo=TZ)
        self.assertEqual(dt.utcoffset(), timedelta(hours=1))

    def test_march29_midnight_utc(self):
        """March 29 midnight CET = 23:00 UTC March 28."""
        ts = midnight_ts(SPRING_FWD_DATE)
        expected = datetime(2026, 3, 28, 23, 0, 0, tzinfo=UTC)
        self.assertEqual(ts, int(expected.timestamp() * 1000))

    def test_summer_midnight_is_cest(self):
        """June 15 midnight is CEST (+02:00)."""
        dt = datetime(2026, 6, 15, 0, 0, 0, tzinfo=TZ)
        self.assertEqual(dt.utcoffset(), timedelta(hours=2))

    def test_winter_midnight_is_cet(self):
        """January 15 midnight is CET (+01:00)."""
        dt = datetime(2026, 1, 15, 0, 0, 0, tzinfo=TZ)
        self.assertEqual(dt.utcoffset(), timedelta(hours=1))


class TestHourMappingSpringForward(unittest.TestCase):
    """Hour mapping on DST spring-forward day."""

    def test_pre_transition_hours_are_cet(self):
        """Hours 0-1 are in CET (+01:00)."""
        for h in [0, 1]:
            result = map_hour(SPRING_FWD_DATE, h)
            self.assertEqual(result.hour, h)
            self.assertEqual(result.utcoffset(), timedelta(hours=1))

    def test_post_transition_hours_are_cest(self):
        """Hours 3-23 are in CEST (+02:00)."""
        for h in range(3, 24):
            result = map_hour(SPRING_FWD_DATE, h)
            self.assertEqual(result.hour, h)
            self.assertEqual(result.utcoffset(), timedelta(hours=2))

    def test_gap_hour_2_creates_duplicate_utc(self):
        """Hour 2 doesn't exist in local time — maps to same UTC as hour 3.

        This is the key DST anomaly: API index 2 and index 3 both produce
        01:00 UTC. When importing to HA statistics, the second overwrites
        the first (or causes StaleDataError).
        """
        h2 = map_hour(SPRING_FWD_DATE, 2)
        h3 = map_hour(SPRING_FWD_DATE, 3)
        self.assertEqual(
            h2.astimezone(UTC), h3.astimezone(UTC),
            "Hours 2 and 3 should have same UTC on spring-forward day"
        )

    def test_no_other_utc_duplicates(self):
        """Only hours 2 and 3 share a UTC timestamp."""
        utc_times = {}
        for h in range(24):
            utc = map_hour(SPRING_FWD_DATE, h).astimezone(UTC)
            key = utc.isoformat()
            if key in utc_times:
                # Only 2 and 3 should duplicate
                self.assertIn(h, [3])
                self.assertIn(utc_times[key], [2])
            utc_times[key] = h

    def test_utc_monotonic_except_gap(self):
        """UTC timestamps are monotonically increasing, except the gap."""
        utc_list = [map_hour(SPRING_FWD_DATE, h).astimezone(UTC) for h in range(24)]
        for i in range(1, 24):
            if i == 3:  # Duplicate with hour 2
                self.assertEqual(utc_list[i], utc_list[i-1])
            else:
                self.assertGreater(utc_list[i], utc_list[i-1],
                                   f"Hour {i} should be after hour {i-1}")


class TestHourMappingNormalDays(unittest.TestCase):
    """Hour mapping on normal (non-transition) days."""

    def test_winter_24_unique_utc(self):
        """Winter day: all 24 hours have unique UTC timestamps."""
        utc_set = {map_hour(WINTER_DATE, h).astimezone(UTC) for h in range(24)}
        self.assertEqual(len(utc_set), 24)

    def test_summer_24_unique_utc(self):
        """Summer day: all 24 hours have unique UTC timestamps."""
        utc_set = {map_hour(SUMMER_DATE, h).astimezone(UTC) for h in range(24)}
        self.assertEqual(len(utc_set), 24)

    def test_winter_hours_are_cet(self):
        """All winter hours are CET (+01:00)."""
        for h in range(24):
            self.assertEqual(map_hour(WINTER_DATE, h).utcoffset(), timedelta(hours=1))

    def test_summer_hours_are_cest(self):
        """All summer hours are CEST (+02:00)."""
        for h in range(24):
            self.assertEqual(map_hour(SUMMER_DATE, h).utcoffset(), timedelta(hours=2))

    def test_fall_back_24_unique_utc(self):
        """Fall-back day: default fold=0 means 24 unique UTC timestamps."""
        utc_set = {map_hour(FALL_BACK_DATE, h).astimezone(UTC) for h in range(24)}
        self.assertEqual(len(utc_set), 24)


class TestReplaceVsConstructor(unittest.TestCase):
    """Verify .replace() and constructor produce identical results with ZoneInfo."""

    def test_spring_forward_day_equivalent(self):
        """ZoneInfo normalizes .replace() correctly on DST days too."""
        start = datetime(2026, 3, 28, 15, 0, 0, tzinfo=TZ)
        target_cest = start + timedelta(days=1)

        ts_replace = int(
            target_cest.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(TZ).timestamp() * 1000
        )
        ts_ctor = midnight_ts(SPRING_FWD_DATE)

        # With ZoneInfo, both produce the same result
        self.assertEqual(ts_replace, ts_ctor)

    def test_normal_day_equivalent(self):
        """On normal days, replace and constructor are obviously equivalent."""
        target = datetime(2026, 1, 15, 10, 0, 0, tzinfo=TZ)
        ts_replace = int(
            target.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(TZ).timestamp() * 1000
        )
        ts_ctor = midnight_ts(WINTER_DATE)
        self.assertEqual(ts_replace, ts_ctor)


if __name__ == "__main__":
    unittest.main()
