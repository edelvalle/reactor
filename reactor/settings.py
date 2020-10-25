from django.conf import settings


def get(name, default=None):
    return getattr(settings, f'REACTOR_{name}', default)


LOGIN_URL = settings.LOGIN_URL
INCLUDE_TURBOLINKS = get('INCLUDE_TURBOLINKS', False)
USE_HTML_DIFF = get('USE_HTML_DIFF', True)
USE_HMIN = get('USE_HMIN', True)
AUTO_BROADCAST = get('AUTO_BROADCAST', False)


if isinstance(AUTO_BROADCAST, bool):
    AUTO_BROADCAST = {
        # model_a
        # model_a.del
        # model_a.new
        'MODEL': AUTO_BROADCAST,

        # model_a.1234
        'MODEL_PK': AUTO_BROADCAST,

        # model_b.1234.model_a_set
        # model_b.1234.model_a_set.new
        # model_b.1234.model_a_set.del
        'RELATED': AUTO_BROADCAST,

        # model_b.1234.model_a_set
        # model_a.1234.model_b_set
        'M2M': AUTO_BROADCAST,
    }
