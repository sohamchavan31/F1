import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "f1_project.settings")
django.setup()

from api.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http":      get_asgi_application(),
    "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
