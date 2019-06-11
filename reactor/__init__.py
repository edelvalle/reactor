
from django.conf import settings

from .component import (  # noqa
    Component, AuthComponent, StaffComponent, on_commit, broadcast
)


if getattr(settings, 'REACTOR_AUTO_BROADCAST', False):
    import reactor.auto_broadcast  # noqa
