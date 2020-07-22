from django.core.checks import Warning, register
from django.conf import settings as dj_settings

from . import settings
from .component import (  # noqa
    Component, AuthComponent, StaffComponent, on_commit, broadcast
)


if settings.AUTO_BROADCAST:
    import reactor.auto_broadcast  # noqa


@register()
def check_for_turbolinks_middleware(app_configs, **kwargs):
    reactor_middleware = 'reactor.middleware.turbolinks_middleware'
    problem = (
        settings.INCLUDE_TURBOLINKS and
        reactor_middleware not in dj_settings.MIDDLEWARE
    )
    if problem:
        return [Warning(
            'Turbolinks middleware is missing',
            hint=(
                f'When you set REACTOR_INCLUDE_TURBOLINKS, during the '
                f'redirects the URL of the browser could be that is not up to '
                f'date. To avoid that include `{reactor_middleware}` in the '
                f'`MIDDLEWARE`.'
            ),
            id='reactor.W001',
        )]
    else:
        return []
