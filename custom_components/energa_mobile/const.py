"""Constants for the Energa Mobile integration."""

DOMAIN = "energa_mobile"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"

BASE_URL = "https://api-mojlicznik.energa-operator.pl"
LOGIN_ENDPOINT = "/dp/apihelper/UserLogin"
DATA_ENDPOINT = "/dp/resources/user/data"

# Endpoint do wykresów (potwierdzony w Fiddler i starej integracji)
HISTORY_ENDPOINT = "/dp/resources/mchart"

# Parametry 'mo' (Meter Object) - Klucz do działania wykresów!
# Wzięte z pliku stats_modes.py starej integracji
MO_CONSUMPTION = "A+"
MO_PRODUCTION = "A-"

HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept-Language": "pl-PL;q=1.0",
    "Accept": "*/*",
    "Content-Type": "application/json"
}