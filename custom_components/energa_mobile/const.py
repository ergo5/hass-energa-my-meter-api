"""Constants for the Energa Mobile integration."""

DOMAIN = "energa_mobile"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"

BASE_URL = "https://api-mojlicznik.energa-operator.pl"
LOGIN_ENDPOINT = "/dp/apihelper/UserLogin"
DATA_ENDPOINT = "/dp/resources/user/data"

# Endpoint do wykresów
HISTORY_ENDPOINT = "/dp/resources/mchart"

# Kody OBIS (Meter Object) - Kluczowe dla rozróżnienia danych!
# 1-0:1.8.0*255 = Pobór (Import)
# 1-0:2.8.0*255 = Produkcja (Eksport)
MO_CONSUMPTION = "1-0:1.8.0*255"
MO_PRODUCTION = "1-0:2.8.0*255"

HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept-Language": "pl-PL;q=1.0",
    "Accept": "*/*",
    "Content-Type": "application/json"
}