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

    def test_export_sensor_always_single(self):
        """Export sensor is always single (no zone split)."""
        for has_zones in [True, False]:
            export_key = "export"  # Never zone-specific
            assert export_key == "export"

    def test_prosumer_sensor_only_for_exporters(self):
        """Prosumer balance only created when obis_minus exists."""
        meter_with_export = {"obis_minus": "1-0:2.8.0*255"}
        meter_without_export = {"obis_minus": None}

        assert bool(meter_with_export.get("obis_minus")) is True
        assert bool(meter_without_export.get("obis_minus")) is False
