from django.conf import settings

from .schemas import AutoBroadcast

DEBUG = settings.DEBUG
DEFAULT = {
    "TRANSPILER_CACHE_SIZE": 1024,
    "USE_HTML_DIFF": True,
    "USE_HMIN": False,
    "BOOST_PAGES": False,
    "AUTO_BROADCAST": AutoBroadcast(),
}

REACTOR = DEFAULT | getattr(settings, "REACTOR", {})
LOGIN_URL = settings.LOGIN_URL

TRANSPILER_CACHE_SIZE: int = REACTOR["TRANSPILER_CACHE_SIZE"]
USE_HTML_DIFF: bool = REACTOR["USE_HTML_DIFF"]
USE_HMIN: bool = REACTOR["USE_HMIN"]
BOOST_PAGES: bool = REACTOR["BOOST_PAGES"]
AUTO_BROADCAST: AutoBroadcast = REACTOR["AUTO_BROADCAST"]
