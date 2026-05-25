from django.urls import path
from api import views

urlpatterns = [
    path("sessions/",                              views.session_list),
    path("sessions/<str:session_id>/",             views.session_detail),
    path("track-map/<str:event>/",                 views.track_map),
    path("track-map/<str:event>/<int:year>/",      views.track_map),
    path("frame/<str:session_id>/<int:t_ms>/",     views.frame_at),
]
