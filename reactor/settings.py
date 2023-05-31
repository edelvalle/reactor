from django.conf import settings
from django.core.cache import InvalidCacheBackendError, caches
from django.core.cache.backends.locmem import LocMemCache

DEBUG = settings.DEBUG
DEFAULT = {
    "USE_HTML_DIFF": True,
    "USE_HMIN": False,
    "BOOST_PAGES": False,
    "RECEIVER_PREFIX": "recv_",
    "TRANSPILER_CACHE_NAME": "reactor:transpiler",
    "AUTO_BROADCAST": False,
}

REACTOR = DEFAULT | getattr(settings, "REACTOR", {})

LOGIN_URL = settings.LOGIN_URL

RECEIVER_PREFIX: str = REACTOR["RECEIVER_PREFIX"]
USE_HTML_DIFF: bool = REACTOR["USE_HTML_DIFF"]
USE_HMIN: bool = REACTOR["USE_HMIN"]
TRANSPILER_CACHE_NAME: str = REACTOR["TRANSPILER_CACHE_NAME"]
BOOST_PAGES: bool = REACTOR["BOOST_PAGES"]
AUTO_BROADCAST: dict[str, bool] = REACTOR["AUTO_BROADCAST"]


if isinstance(AUTO_BROADCAST, bool):
    AUTO_BROADCAST = {
        # model_a
        "MODEL": AUTO_BROADCAST,
        # model_a.1234
        "MODEL_PK": AUTO_BROADCAST,
        # model-b.9876.model-a-set
        "RELATED": AUTO_BROADCAST,
        # model-b.9876.model-a-set
        # model-a.1234.model-b-set
        "M2M": AUTO_BROADCAST,
    }


try:
    cache = caches["reactor"]
except InvalidCacheBackendError:
    cache = caches["default"]

try:
    transpiler_cache = caches[TRANSPILER_CACHE_NAME]
except InvalidCacheBackendError:
    transpiler_cache = LocMemCache(
        name=TRANSPILER_CACHE_NAME,
        params={"timeout": 3600, "max_entries": 1024, "cull_frequency": 32},
    )
