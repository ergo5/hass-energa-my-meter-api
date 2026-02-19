"""Constants for Energa My Meter integration."""

DOMAIN = "energa_mobile"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_TOKEN = "device_token"
CONF_IMPORT_PRICE = "import_price"  # PLN/kWh for consumption (single-zone G11)
CONF_EXPORT_PRICE = "export_price"  # PLN/kWh for production compensation
CONF_IMPORT_PRICE_1 = "import_price_1"  # PLN/kWh zone 1 / peak (G12w)
CONF_IMPORT_PRICE_2 = "import_price_2"  # PLN/kWh zone 2 / off-peak (G12w)

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
