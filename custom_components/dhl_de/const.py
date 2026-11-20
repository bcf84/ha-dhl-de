"""Constants for the DHL Deutschland integration."""

from __future__ import annotations

DOMAIN = "dhl_de"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30  # minutes
MIN_SCAN_INTERVAL = 10

# OAuth parameters of the official DHL app (same as ioBroker.parcel)
TENANT_URL = "https://login.dhl.de/af5f9bb6-27ad-4af4-9445-008e7a5cddb8/login"
TOKEN_URL = f"{TENANT_URL}/token"
CLIENT_ID = "83471082-5c13-4fce-8dcb-19d2a3fca413"
BASIC_AUTH = "Basic ODM0NzEwODItNWMxMy00ZmNlLThkY2ItMTlkMmEzZmNhNDEzOg=="
REDIRECT_URI = "dhllogin://de.deutschepost.dhl/login"
CODE_VERIFIER = "zmVs5AKfGvv45a9aUvuOid9a_erOirp7XL1sn9kWT_o"
CODE_CHALLENGE = "MAhrhXXZP-Owy-R7ruyB7Fn-Z8ODW6qxCoHg4uXELCw"

LOGIN_URL = (
    f"{TENANT_URL}/authorize?redirect_uri=dhllogin://de.deutschepost.dhl/login"
    "&state=eyJycyI6dHJ1ZSwicnYiOmZhbHNlLCJmaWQiOiJhcHAtbG9naW4tbWVoci1mb290ZXIiLCJoaWQiOiJhcHAtbG9naW4tbWVoci1oZWFkZXIiLCJycCI6ZmFsc2V9"
    f"&client_id={CLIENT_ID}&response_type=code&scope=openid%20offline_access"
    "&claims=%7B%22id_token%22:%7B%22email%22:null,%22post_number%22:null,%22twofa%22:null,"
    "%22service_mask%22:null,%22deactivate_account%22:null,%22last_login%22:null,"
    "%22customer_type%22:null,%22display_name%22:null,%22data_confirmation_required%22:null%7D%7D"
    "&nonce=&login_hint=&prompt=login&ui_locales=de-DE"
    f"&code_challenge={CODE_CHALLENGE}&code_challenge_method=S256"
)

APP_USER_AGENT = "DHLPaket_PROD/1367 CFNetwork/1240.0.4 Darwin/20.6.0"
WEB_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)
IMAGE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
)

SEARCH_URL = "https://www.dhl.de/int-verfolgen/data/search"
ADVICES_URL = "https://www.dhl.de/int-aviseanzeigen/advices?width=414"
TRACKING_LINK = "https://www.dhl.de/de/privatkunden/dhl-sendungsverfolgung.html?piececode={}"

# Akamai bot-detection cookies that cause resets when stale
AKAMAI_COOKIES = {"_abck", "ak_bmsc", "bm_sz"}

# sendungsverlauf.fortschritt -> status
STATUS_REGISTERED = "registered"
STATUS_IN_PREPARATION = "in_preparation"
STATUS_IN_TRANSIT = "in_transit"
STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
STATUS_READY_FOR_PICKUP = "ready_for_pickup"
STATUS_DELIVERED = "delivered"
STATUS_UNKNOWN = "unknown"
FORTSCHRITT_MAP = {
    0: STATUS_REGISTERED,
    1: STATUS_REGISTERED,
    2: STATUS_IN_PREPARATION,
    3: STATUS_IN_TRANSIT,
    4: STATUS_OUT_FOR_DELIVERY,
    5: STATUS_DELIVERED,
}

MAX_LETTER_IMAGES = 10
