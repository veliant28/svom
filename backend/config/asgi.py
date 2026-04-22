import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_application = get_asgi_application()

try:
    from channels.routing import ProtocolTypeRouter, URLRouter

    from apps.support.realtime.auth import TokenQueryAuthMiddleware
    from apps.support.realtime.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_application,
            "websocket": TokenQueryAuthMiddleware(URLRouter(websocket_urlpatterns)),
        }
    )
except ModuleNotFoundError:
    # Fallback for environments where Channels is not installed.
    application = django_asgi_application
