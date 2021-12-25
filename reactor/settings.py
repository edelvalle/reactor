from django.conf import settings

DEFAULT = {
    "USE_HTML_DIFF": True,
    "USE_HMIN": False,
    "TRANSPILER_CACHE_SIZE": 1024,
    "BOOST_PAGES": False,
    "AUTO_BROADCAST": False,
}

REACTOR = DEFAULT | getattr(settings, "REACTOR", {})

LOGIN_URL = settings.LOGIN_URL

USE_HTML_DIFF = REACTOR["USE_HTML_DIFF"]
USE_HMIN = REACTOR["USE_HMIN"]
TRANSPILER_CACHE_SIZE = REACTOR["TRANSPILER_CACHE_SIZE"]
BOOST_PAGES = REACTOR["BOOST_PAGES"]
AUTO_BROADCAST = REACTOR["AUTO_BROADCAST"]


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
