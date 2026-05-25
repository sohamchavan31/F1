from django.urls import path
from api.consumers import ReplayConsumer

# ws://host/ws/replay/<session_id>/
websocket_urlpatterns = [
    path("ws/replay/<str:session_id>/", ReplayConsumer.as_asgi()),
]
