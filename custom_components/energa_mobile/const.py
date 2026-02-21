"""Constants for Energa My Meter integration."""

DOMAIN = "energa_mobile"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_TOKEN = "device_token"
CONF_IMPORT_PRICE = "import_price"  # PLN/kWh for consumption (single-zone G11)
CONF_EXPORT_PRICE = "export_price"  # PLN/kWh for production compensation
CONF_IMPORT_PRICE_1 = "import_price_1"  # PLN/kWh zone 1 / peak (G12w)
CONF_IMPORT_PRICE_2 = "import_price_2"  # PLN/kWh zone 2 / off-peak (G12w)

# Default prices (PLN/kWh) - G12w tariff from 2026-01-01
DEFAULT_IMPORT_PRICE = 1.188
DEFAULT_IMPORT_PRICE_1 = 1.2453  # Zone 1 (peak)
DEFAULT_IMPORT_PRICE_2 = 0.5955  # Zone 2 (off-peak)
DEFAULT_EXPORT_PRICE = 0.95

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


def get_price_for_key(options: dict, data_key: str) -> float:
    """Get the configured price for a given data key."""
    if data_key == "import_1":
        return float(options.get(CONF_IMPORT_PRICE_1, DEFAULT_IMPORT_PRICE_1))
    if data_key == "import_2":
        return float(options.get(CONF_IMPORT_PRICE_2, DEFAULT_IMPORT_PRICE_2))
    if data_key == "export":
        return float(options.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE))
    return float(options.get(CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE))
