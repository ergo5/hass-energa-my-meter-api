"""Constants for Energa My Meter integration."""

DOMAIN = "energa_mobile"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_TOKEN = "device_token"
CONF_IMPORT_PRICE = "import_price"  # PLN/kWh for consumption (single-zone G11)
CONF_EXPORT_PRICE = "export_price"  # PLN/kWh for production compensation
CONF_IMPORT_PRICE_1 = "import_price_1"  # PLN/kWh zone 1 / peak (G12w)
CONF_IMPORT_PRICE_2 = "import_price_2"  # PLN/kWh zone 2 / off-peak (G12w)
CONF_PROSUMER_COEFFICIENT = "prosumer_coefficient"  # Net billing coefficient (0.0-1.0)

# Default prices (PLN/kWh) - G12w tariff from 2026-01-01
DEFAULT_IMPORT_PRICE = 1.188
DEFAULT_IMPORT_PRICE_1 = 1.2453  # Zone 1 (peak)
DEFAULT_IMPORT_PRICE_2 = 0.5955  # Zone 2 (off-peak)
DEFAULT_EXPORT_PRICE = 0.95
DEFAULT_PROSUMER_COEFFICIENT = 0.8

# API endpoints
BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
LOGIN_ENDPOINT = "/apihelper/UserLogin"
SESSION_ENDPOINT = "/apihelper/SessionStatus"
DATA_ENDPOINT = "/resources/user/data"
CHART_ENDPOINT = "/resources/mchart"

# API headers (iOS app user agent)
HEADERS = {
    "User-Agent": "Energa/3.1.2 (pl.energa-operator.mojlicznik; build:1; iOS 16.6.1) Alamofire/5.6.4",
    "Accept": "application/json",
    "Accept-Language": "pl-PL;q=1.0, en-PL;q=0.9",
    "Content-Type": "application/json",
}

# Spike guard: maximum plausible hourly energy consumption in kWh
MAX_HOURLY_KWH = 100


def get_price_for_key(
    options: dict, data_key: str, meter_id: str | None = None
) -> float:
    """Get the configured price for a given data key.

    Supports per-meter pricing: if meter_id is provided, looks for
    meter-specific keys first (e.g. 'meter_30132815_import_price'),
    then falls back to global keys.
    """
    key_map = {
        "import": (CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE),
        "import_1": (CONF_IMPORT_PRICE_1, DEFAULT_IMPORT_PRICE_1),
        "import_2": (CONF_IMPORT_PRICE_2, DEFAULT_IMPORT_PRICE_2),
        "export": (CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE),
        "export_1": (CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE),
        "export_2": (CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE),
    }

    conf_key, default_val = key_map.get(
        data_key, (CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE)
    )

    # Per-meter override: meter_{serial}_{key}
    if meter_id:
        meter_key = f"meter_{meter_id}_{conf_key}"
        if meter_key in options:
            return float(options[meter_key])

    return float(options.get(conf_key, default_val))
