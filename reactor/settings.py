from django.conf import settings


def get(name, default):
    return getattr(settings, f'REACTOR_{name}', default)


LOGIN_URL = settings.LOGIN_URL
INCLUDE_TURBOLINKS = get('INCLUDE_TURBOLINKS', False)
USE_HTML_DIFF = get('USE_HTML_DIFF', False)
AUTO_BROADCAST = get('AUTO_BROADCAST', False)
