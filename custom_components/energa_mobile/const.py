"""Constants for the Energa Mobile integration."""

DOMAIN = "energa_mobile"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
LOGIN_ENDPOINT = "/apihelper/UserLogin"
SESSION_ENDPOINT = "/apihelper/SessionStatus"
DATA_ENDPOINT = "/resources/user/data"
CHART_ENDPOINT = "/resources/mchart"

HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept": "*/*",
    "Accept-Language": "en-US;q=1.0, pl-PL;q=0.9",
    "Content-Type": "application/json"
}