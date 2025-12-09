"""Constants for the Energa Mobile integration."""

DOMAIN = "energa_mobile"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"

BASE_URL = "https://api-mojlicznik.energa-operator.pl"
LOGIN_ENDPOINT = "/dp/apihelper/UserLogin"
DATA_ENDPOINT = "/dp/resources/user/data"
HISTORY_ENDPOINT = "/dp/resources/mchart"

# KODY OBIS (Potwierdzone w dekompilacji APK)
# Aplikacja używa tych kodów w polu 'mo'.
MO_CONSUMPTION = "1-0:1.8.0*255"  # Pobór z sieci
MO_PRODUCTION = "1-0:2.8.0*255"   # Oddanie do sieci

HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept-Language": "pl-PL;q=1.0",
    "Accept": "*/*",
    "Content-Type": "application/json"
}