"""Deep QA tests for EnergaPriceSensor logic (issue #28).

Tests price lookup, edge cases, unique_id collisions, regression.
Runs via pytest without HA runtime (const.py is pure Python).
"""

from custom_components.energa_mobile.const import (
    CONF_EXPORT_PRICE,
    CONF_IMPORT_PRICE,
    CONF_IMPORT_PRICE_1,
    CONF_IMPORT_PRICE_2,
    CONF_PROSUMER_COEFFICIENT,
    DEFAULT_EXPORT_PRICE,
    DEFAULT_IMPORT_PRICE,
    DEFAULT_IMPORT_PRICE_1,
    DEFAULT_IMPORT_PRICE_2,
    DEFAULT_PROSUMER_COEFFICIENT,
    get_price_for_key,
)


class TestPriceDefaults:
    """All 6 data_key paths return correct defaults."""

    def test_import_default(self):
        assert get_price_for_key({}, "import") == DEFAULT_IMPORT_PRICE

    def test_import_1_default(self):
        assert get_price_for_key({}, "import_1") == DEFAULT_IMPORT_PRICE_1

    def test_import_2_default(self):
        assert get_price_for_key({}, "import_2") == DEFAULT_IMPORT_PRICE_2

    def test_export_default(self):
        assert get_price_for_key({}, "export") == DEFAULT_EXPORT_PRICE

    def test_export_1_same_as_export(self):
        assert get_price_for_key({}, "export_1") == DEFAULT_EXPORT_PRICE

    def test_export_2_same_as_export(self):
        assert get_price_for_key({}, "export_2") == DEFAULT_EXPORT_PRICE


class TestPriceCustom:
    """User-set prices override defaults correctly."""

    def test_custom_import(self):
        assert get_price_for_key({CONF_IMPORT_PRICE: 2.0}, "import") == 2.0

    def test_custom_zone_1(self):
        assert get_price_for_key({CONF_IMPORT_PRICE_1: 2.5}, "import_1") == 2.5

    def test_custom_zone_2(self):
        assert get_price_for_key({CONF_IMPORT_PRICE_2: 1.1}, "import_2") == 1.1

    def test_custom_export(self):
        assert get_price_for_key({CONF_EXPORT_PRICE: 0.5}, "export") == 0.5


class TestPerMeterOverride:
    """Per-meter pricing takes precedence over global."""

    def test_per_meter_takes_precedence(self):
        opts = {CONF_IMPORT_PRICE: 1.0, "meter_ABC123_import_price": 3.33}
        assert get_price_for_key(opts, "import", meter_id="ABC123") == 3.33

    def test_other_meter_uses_global(self):
        opts = {CONF_IMPORT_PRICE: 1.0, "meter_ABC123_import_price": 3.33}
        assert get_price_for_key(opts, "import", meter_id="XYZ999") == 1.0

    def test_no_meter_id_uses_global(self):
        opts = {CONF_IMPORT_PRICE: 1.0, "meter_ABC123_import_price": 3.33}
        assert get_price_for_key(opts, "import") == 1.0

    def test_per_meter_zone_1(self):
        opts = {CONF_IMPORT_PRICE_1: 1.0, "meter_12345_import_price_1": 4.44}
        assert get_price_for_key(opts, "import_1", meter_id="12345") == 4.44

    def test_per_meter_export(self):
        opts = {CONF_EXPORT_PRICE: 0.9, "meter_99_export_price": 0.1}
        assert get_price_for_key(opts, "export", meter_id="99") == 0.1


class TestCoefficientLogic:
    """Prosumer coefficient lookup (mimics EnergaPriceSensor.native_value)."""

    def test_default_coefficient(self):
        opts = {}
        val = float(opts.get(CONF_PROSUMER_COEFFICIENT, DEFAULT_PROSUMER_COEFFICIENT))
        assert val == 0.8

    def test_custom_coefficient(self):
        opts = {CONF_PROSUMER_COEFFICIENT: 0.7}
        val = float(opts.get(CONF_PROSUMER_COEFFICIENT, DEFAULT_PROSUMER_COEFFICIENT))
        assert val == 0.7

    def test_coefficient_as_string(self):
        opts = {CONF_PROSUMER_COEFFICIENT: "0.65"}
        val = float(opts.get(CONF_PROSUMER_COEFFICIENT, DEFAULT_PROSUMER_COEFFICIENT))
        assert val == 0.65

    def test_coefficient_zero(self):
        opts = {CONF_PROSUMER_COEFFICIENT: 0}
        val = float(opts.get(CONF_PROSUMER_COEFFICIENT, DEFAULT_PROSUMER_COEFFICIENT))
        assert val == 0.0

    def test_coefficient_one(self):
        opts = {CONF_PROSUMER_COEFFICIENT: 1.0}
        val = float(opts.get(CONF_PROSUMER_COEFFICIENT, DEFAULT_PROSUMER_COEFFICIENT))
        assert val == 1.0


class TestEdgeCases:
    """Edge cases and type coercion."""

    def test_unknown_key_defaults_to_import(self):
        assert get_price_for_key({}, "nonexistent_key") == DEFAULT_IMPORT_PRICE

    def test_string_price_coerced(self):
        assert get_price_for_key({CONF_IMPORT_PRICE: "1.999"}, "import") == 1.999

    def test_integer_price_coerced(self):
        assert get_price_for_key({CONF_IMPORT_PRICE: 2}, "import") == 2.0

    def test_zero_price_valid(self):
        assert get_price_for_key({CONF_IMPORT_PRICE: 0}, "import") == 0.0

    def test_negative_price_valid(self):
        """Negative price is edge but shouldn't crash."""
        assert get_price_for_key({CONF_IMPORT_PRICE: -0.5}, "import") == -0.5

    def test_very_large_price(self):
        assert get_price_for_key({CONF_IMPORT_PRICE: 99999.99}, "import") == 99999.99

    def test_return_type_is_float(self):
        result = get_price_for_key({CONF_IMPORT_PRICE: 1}, "import")
        assert isinstance(result, float)


class TestUniqueIdCollisions:
    """Verify unique_id patterns don't collide across sensor types."""

    METER_IDS = ["30132815", "99887766"]
    PRICE_KEYS = ["import", "import_1", "import_2", "export", "prosumer_coefficient"]
    LIVE_KEYS = ["total_plus", "total_minus", "daily_pobor", "daily_produkcja"]
    STATS_KEYS = ["import", "import_1", "import_2", "export", "export_1", "export_2"]

    def test_price_uids_unique(self):
        """All price sensor unique_ids are distinct."""
        uids = [
            f"energa_{mid}_{dk}_price"
            for mid in self.METER_IDS
            for dk in self.PRICE_KEYS
        ]
        assert len(uids) == len(set(uids))

    def test_no_collision_with_live(self):
        """Price IDs don't collide with live sensor IDs."""
        price_uids = {f"energa_{m}_{k}_price" for m in self.METER_IDS for k in self.PRICE_KEYS}
        live_uids = {f"energa_{m}_{k}_live" for m in self.METER_IDS for k in self.LIVE_KEYS}
        assert price_uids.isdisjoint(live_uids)

    def test_no_collision_with_stats(self):
        """Price IDs don't collide with statistics sensor IDs."""
        price_uids = {f"energa_{m}_{k}_price" for m in self.METER_IDS for k in self.PRICE_KEYS}
        stats_uids = {f"energa_{m}_{k}_stats" for m in self.METER_IDS for k in self.STATS_KEYS}
        assert price_uids.isdisjoint(stats_uids)

    def test_no_collision_with_info(self):
        """Price IDs don't collide with info sensor IDs."""
        info_keys = ["address", "tariff", "ppe", "meter_serial", "contract_date"]
        price_uids = {f"energa_{m}_{k}_price" for m in self.METER_IDS for k in self.PRICE_KEYS}
        info_uids = {f"energa_{m}_{k}_info" for m in self.METER_IDS for k in info_keys}
        assert price_uids.isdisjoint(info_uids)

    def test_no_collision_with_balance(self):
        """Price IDs don't collide with prosumer balance sensor ID."""
        price_uids = {f"energa_{m}_{k}_price" for m in self.METER_IDS for k in self.PRICE_KEYS}
        balance_uids = {f"energa_{m}_prosumer_balance" for m in self.METER_IDS}
        assert price_uids.isdisjoint(balance_uids)


class TestProsumerBalanceRegression:
    """Regression: prosumer balance formula unchanged after adding price sensors."""

    @staticmethod
    def calc(imp, exp, coeff=0.8, bl_imp=0.0, bl_exp=0.0):
        return round(((exp - bl_exp) * coeff) - (imp - bl_imp), 2)

    def test_positive(self):
        assert self.calc(100, 200) == 60.0

    def test_negative(self):
        assert self.calc(500, 200) == -340.0

    def test_zero(self):
        assert self.calc(80, 100) == 0.0

    def test_with_baselines(self):
        assert self.calc(45507, 29580, bl_imp=45177, bl_exp=29389) == -177.2

    def test_gednet_scenario(self):
        assert self.calc(10010, 10840, coeff=0.7, bl_imp=10000, bl_exp=10000) == 578.0
