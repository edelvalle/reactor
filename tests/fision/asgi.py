import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fision.settings')

from reactor.asgi import get_asgi_application  # noqa

application = get_asgi_application()
