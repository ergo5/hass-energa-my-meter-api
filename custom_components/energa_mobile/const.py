"""Constants for the Energa Mobile integration."""

DOMAIN = "energa_mobile"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"

# Nowe API (odkryte 02.12.2025)
BASE_URL = "https://api-mojlicznik.energa-operator.pl"
LOGIN_ENDPOINT = "/dp/apihelper/UserLogin"
DATA_ENDPOINT = "/dp/resources/user/data"
# NOWY ENDPOINT DANYCH GODZINOWYCH
HISTORY_ENDPOINT = "/dp/resources/user/measurements" 

# Nagłówki emulujące aplikację iOS
HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept-Language": "pl-PL;q=1.0",
    "Accept": "*/*",
    "Content-Type": "application/json"
}