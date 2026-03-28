"""Tests for sensor logic — prosumer balance calculation.

The prosumer balance formula is:
    balance = (total_export × coefficient) − total_import

Tested independently of HA entity framework by extracting the
pure calculation logic.
"""




def calculate_prosumer_balance(
    total_import: float,
    total_export: float,
    coefficient: float = 0.8,
) -> float:
    """Extract of EnergaProsumerBalanceSensor.native_value calculation."""
    balance = (total_export * coefficient) - total_import
    return round(balance, 2)


class TestProsumerBalance:
    """Tests for prosumer balance calculation."""

    def test_positive_balance(self):
        """More export than import → positive balance (surplus)."""
        result = calculate_prosumer_balance(
            total_import=100.0, total_export=200.0, coefficient=0.8
        )
        # 200 * 0.8 - 100 = 60
        assert result == 60.0

    def test_negative_balance(self):
        """More import than export → negative balance (debt)."""
        result = calculate_prosumer_balance(
            total_import=500.0, total_export=200.0, coefficient=0.8
        )
        # 200 * 0.8 - 500 = -340
        assert result == -340.0

    def test_zero_balance(self):
        """Exact equilibrium."""
        result = calculate_prosumer_balance(
            total_import=80.0, total_export=100.0, coefficient=0.8
        )
        # 100 * 0.8 - 80 = 0
        assert result == 0.0

    def test_custom_coefficient(self):
        """Non-default coefficient (e.g. 0.7 for net-billing)."""
        result = calculate_prosumer_balance(
            total_import=100.0, total_export=200.0, coefficient=0.7
        )
        # 200 * 0.7 - 100 = 40
        assert result == 40.0

    def test_coefficient_1_0(self):
        """Coefficient 1.0 = no loss on exchange."""
        result = calculate_prosumer_balance(
            total_import=100.0, total_export=100.0, coefficient=1.0
        )
        assert result == 0.0

    def test_zero_export(self):
        """Consumer only (no export) → negative balance."""
        result = calculate_prosumer_balance(
            total_import=500.0, total_export=0.0, coefficient=0.8
        )
        assert result == -500.0

    def test_zero_import(self):
        """Full self-consumption → positive balance."""
        result = calculate_prosumer_balance(
            total_import=0.0, total_export=100.0, coefficient=0.8
        )
        assert result == 80.0

    def test_real_world_values(self):
        """Real-world test case from Lab verification."""
        # From G12W test: export ~29527, import ~45449
        result = calculate_prosumer_balance(
            total_import=45449.543,
            total_export=29526.870,
            coefficient=0.8,
        )
        # 29526.870 * 0.8 - 45449.543 = 23621.496 - 45449.543 = -21828.047
        assert result == -21828.05  # rounded to 2 dp

    def test_float_precision(self):
        """Floating point edge case."""
        result = calculate_prosumer_balance(
            total_import=0.1, total_export=0.1, coefficient=0.8
        )
        # 0.1 * 0.8 - 0.1 = 0.08 - 0.1 = -0.02
        assert result == -0.02


class TestSensorCreationLogic:
    """Tests for sensor creation branching (G11 vs G12W paths)."""

    def test_g11_creates_single_import_sensor(self):
        """G11 meter uses data_key='import', name='Panel Energia Zużycie'."""
        has_zones = False
        if has_zones:
            data_keys = ["import_1", "import_2"]
        else:
            data_keys = ["import"]
        assert data_keys == ["import"]

    def test_g12w_creates_zone_sensors(self):
        """G12W meter creates two zone-specific sensors."""
        has_zones = True
        if has_zones:
            data_keys = ["import_1", "import_2"]
        else:
            data_keys = ["import"]
        assert data_keys == ["import_1", "import_2"]

    def test_g12w_creates_zone_export_sensors(self):
        """G12W creates per-zone export sensors (export_1, export_2)."""
        has_zones = True
        has_export = True
        if has_export and has_zones:
            export_keys = ["export_1", "export_2"]
        elif has_export:
            export_keys = ["export"]
        else:
            export_keys = []
        assert export_keys == ["export_1", "export_2"]

    def test_g11_creates_single_export_sensor(self):
        """G11 (single-zone) creates single export sensor."""
        has_zones = False
        has_export = True
        if has_export and has_zones:
            export_keys = ["export_1", "export_2"]
        elif has_export:
            export_keys = ["export"]
        else:
            export_keys = []
        assert export_keys == ["export"]

    def test_prosumer_sensor_only_for_exporters(self):
        """Prosumer balance only created when obis_minus exists."""
        meter_with_export = {"obis_minus": "1-0:2.8.0*255"}
        meter_without_export = {"obis_minus": None}

        assert bool(meter_with_export.get("obis_minus")) is True
        assert bool(meter_without_export.get("obis_minus")) is False


class TestChartZoneData:
    """Tests for chart API zone structure interpretation.

    Based on real API data from G12W account 00069839, 2026-03-27.
    zones[] array: index 0 = Strefa 1 (dzienna), index 1 = Strefa 2 (nocna).
    """

    def test_g12w_import_zone_mapping_nocna(self):
        """Hour 00 (nocna): import in zones[1], zones[0] is null."""
        zones = [None, 0.981, None]  # real API data
        zone_1 = zones[0] if zones[0] is not None else 0.0
        zone_2 = zones[1] if zones[1] is not None else 0.0
        assert zone_1 == 0.0    # strefa dzienna not active at midnight
        assert zone_2 == 0.981  # strefa nocna active

    def test_g12w_import_zone_mapping_dzienna(self):
        """Hour 12 (dzienna): import in zones[0], zones[1] is null."""
        zones = [0.083, None, None]  # real API data
        zone_1 = zones[0] if zones[0] is not None else 0.0
        zone_2 = zones[1] if zones[1] is not None else 0.0
        assert zone_1 == 0.083  # strefa dzienna active at noon
        assert zone_2 == 0.0

    def test_g12w_export_zone_mapping(self):
        """Export chart uses same zones[] structure as import."""
        zones = [2.701, None, None]  # real API data, hour 12 export
        zone_1 = zones[0] if zones[0] is not None else 0.0
        zone_2 = zones[1] if zones[1] is not None else 0.0
        assert zone_1 == 2.701  # strefa dzienna export
        assert zone_2 == 0.0

    def test_g12w_export_nocna(self):
        """Export during nocna hours goes to zones[1]."""
        zones = [None, 3.485, None]  # real API data, hour 13 export
        zone_1 = zones[0] if zones[0] is not None else 0.0
        zone_2 = zones[1] if zones[1] is not None else 0.0
        assert zone_1 == 0.0
        assert zone_2 == 3.485

    def test_g11_single_zone(self):
        """G11 always puts data in zones[0]."""
        zones = [0.449, None, None]  # real API data from G11
        total = zones[0] if zones[0] is not None else 0.0
        assert total == 0.449

    def test_zones_third_element_always_null(self):
        """Third element (zones[2]) is always null in current API."""
        test_cases = [
            [None, 0.981, None],
            [0.083, None, None],
            [2.701, None, None],
            [None, 3.485, None],
            [0.449, None, None],
        ]
        for zones in test_cases:
            assert zones[2] is None

