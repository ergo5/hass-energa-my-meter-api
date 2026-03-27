"""Tests for get_price_for_key — pricing logic."""

import pytest

from custom_components.energa_mobile.const import (
    CONF_IMPORT_PRICE,
    CONF_IMPORT_PRICE_1,
    CONF_IMPORT_PRICE_2,
    CONF_EXPORT_PRICE,
    DEFAULT_IMPORT_PRICE,
    DEFAULT_IMPORT_PRICE_1,
    DEFAULT_IMPORT_PRICE_2,
    DEFAULT_EXPORT_PRICE,
    get_price_for_key,
)


class TestGetPriceForKey:
    """Tests for get_price_for_key()."""

    def test_default_import_price(self):
        """Returns default import price when no options set."""
        result = get_price_for_key({}, "import")
        assert result == DEFAULT_IMPORT_PRICE

    def test_default_zone_prices(self):
        """Returns default zone prices."""
        assert get_price_for_key({}, "import_1") == DEFAULT_IMPORT_PRICE_1
        assert get_price_for_key({}, "import_2") == DEFAULT_IMPORT_PRICE_2

    def test_default_export_price(self):
        """Returns default export price."""
        assert get_price_for_key({}, "export") == DEFAULT_EXPORT_PRICE

    def test_custom_import_price(self):
        """Returns custom price from options."""
        options = {CONF_IMPORT_PRICE: 1.50}
        assert get_price_for_key(options, "import") == 1.50

    def test_custom_zone_prices(self):
        """Returns custom zone prices."""
        options = {CONF_IMPORT_PRICE_1: 1.30, CONF_IMPORT_PRICE_2: 0.60}
        assert get_price_for_key(options, "import_1") == 1.30
        assert get_price_for_key(options, "import_2") == 0.60

    def test_per_meter_override(self):
        """Per-meter price takes precedence over global price."""
        options = {
            CONF_IMPORT_PRICE: 1.00,
            "meter_30132815_import_price": 2.00,
        }
        # With meter_id => per-meter
        assert get_price_for_key(options, "import", meter_id="30132815") == 2.00
        # Without meter_id => global
        assert get_price_for_key(options, "import") == 1.00

    def test_per_meter_fallback_to_global(self):
        """Falls back to global when no per-meter key exists."""
        options = {CONF_IMPORT_PRICE: 1.50}
        result = get_price_for_key(options, "import", meter_id="99999999")
        assert result == 1.50

    def test_unknown_data_key_defaults_to_import(self):
        """Unknown data_key falls back to import price."""
        result = get_price_for_key({}, "unknown_key")
        assert result == DEFAULT_IMPORT_PRICE

    def test_string_price_converted_to_float(self):
        """Prices stored as strings are converted to float."""
        options = {CONF_IMPORT_PRICE: "1.234"}
        assert get_price_for_key(options, "import") == 1.234
