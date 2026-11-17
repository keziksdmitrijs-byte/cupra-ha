"""Constants for the Cupra integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "cupra"
VERSION = "0.2.2"
USER_AGENT = f"HA-Cupra/{VERSION}"

# --- EU Data Act portal ------------------------------------------------------
# The portal moved from eu-data-act.drivesomethinggreater.com (Nov 2026); the old
# host only redirects now, so its cookies/callback no longer match.
EUDA_BASE_URL = "https://eu-data-act.vwgroup-datahub.com"
EUDA_HOSTS = frozenset({"eu-data-act.vwgroup-datahub.com", "eu-data-act.drivesomethinggreater.com"})
IDENTITY_BASE = "https://identity.vwgroup.io"
EUDA_CALLBACK_PATH = "/services/callbacklogin"
OIDC_AUTHORIZE_URL = IDENTITY_BASE + "/oidc/v1/authorize"
EUDA_CLIENT_ID = "f85e5b69-e3b2-43aa-9c0d-1b7d0e0b576f@apps_vw-dilab_com"
EUDA_SCOPE = "openid cars profile"
EUDA_REDIRECT_URI = EUDA_BASE_URL + "/login"
EUDA_VEHICLES_PATH = "/proxy_api/consent/me/vehicles?viewPosition=FRONT_LEFT"
EUDA_RELATION_PATH = "/proxy_api/vum/v2/users/me/relations/{vin}"
EUDA_METADATA_PATH = "/proxy_api/euda-apim/datarequest/vehicles/{vin}/metadata/{type}"
# "partial" = customised (continuous) request, "all" = one-off "Get your data" file.
EUDA_REQUEST_TYPES = ("partial", "all")
EUDA_LIST_PATH = "/proxy_api/euda-apim/datadelivery/vehicles/{vin}/{identifier}/list"
EUDA_DOWNLOAD_PATH = "/proxy_api/euda-apim/datadelivery/vehicles/{vin}/{identifier}/download"
EUDA_NO_CONTENT_SUFFIX = "_no_content_found.zip"

# --- My Cupra app backend (OLA) ---------------------------------------------
OLA_BASE = "https://ola.prod.code.seat.cloud.vwgroup.com"
OLA_CLIENT_ID = "3c756d46-f1ba-4d78-9f9a-cff0d5292d51@apps_vw-dilab_com"
OLA_SCOPE = "openid profile nickname birthdate phone"
OLA_REDIRECT_URI = "cupra://oauth-callback"
OLA_TOKEN_URL = OLA_BASE + "/authorization/api/v1/token"
OLA_USERINFO_URL = "https://identity-userinfo.vwgroup.io/oidc/userinfo"
OLA_APP_VERSION = "2.20.3"
OLA_USER_AGENT = f"OLACupra/{OLA_APP_VERSION} (Android 14; SM-G960F; samsung) Mobile"

# --- Config entry keys -------------------------------------------------------
CONF_VIN = "vin"
CONF_IDENTIFIER = "identifier"
CONF_NICKNAME = "nickname"
CONF_COUNTRY = "country"
CONF_USE_OLA = "use_ola"
CONF_SPIN = "spin"
CONF_APPCHECK = "appcheck_token"
CONF_MODEL = "model"
CONF_POWERTRAIN = "powertrain"
CONF_OLA_INTERVAL = "ola_interval"

DEFAULT_COUNTRY = "de"
DEFAULT_LANGUAGE = "en"
CONF_LANGUAGE = "language"
DEFAULT_OLA_INTERVAL = 10  # minutes

# Portal publishes a ZIP every 15 minutes; we check the listing every 5.
EUDA_POLL_INTERVAL = timedelta(minutes=5)
UPDATE_INTERVAL = timedelta(minutes=5)
TRANSIENT_STATUSES = frozenset({404, 429, 500, 502, 503, 504})
STALE_AFTER = timedelta(hours=12)

MODEL_AUTO = "auto"
MODELS = {
    "born": {"name": "Born", "body": "hatch", "powertrain": "ev"},
    "tavascan": {"name": "Tavascan", "body": "coupe_suv", "powertrain": "ev"},
    "raval": {"name": "Raval", "body": "hatch", "powertrain": "ev"},
    "terramar": {"name": "Terramar", "body": "suv", "powertrain": None},
    "formentor": {"name": "Formentor", "body": "coupe_suv", "powertrain": None},
    "leon": {"name": "Leon", "body": "hatch", "powertrain": None},
    "leon_st": {"name": "Leon Sportstourer", "body": "estate", "powertrain": None},
    "ateca": {"name": "Ateca", "body": "suv", "powertrain": "ice"},
}
POWERTRAINS = ("auto", "ev", "phev", "ice")

PLATFORMS = ["sensor", "binary_sensor", "device_tracker", "lock", "switch", "button"]

FRONTEND_URL = "/cupra_frontend"
CARD_FILENAME = "cupra-card.js"
