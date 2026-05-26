from django.urls import path
from api import views

urlpatterns = [
    # ── Replay ──────────────────────────────────────────────────────────────
    path("sessions/",                              views.session_list),
    path("sessions/<str:session_id>/",             views.session_detail),
    path("track-map/<str:event>/",                 views.track_map),
    path("track-map/<str:event>/<int:year>/",      views.track_map),
    path("frame/<str:session_id>/<int:t_ms>/",     views.frame_at),

    # ── Encyclopedia ─────────────────────────────────────────────────────────
    path("encyclopedia/seasons/",                          views.seasons_list),
    path("encyclopedia/seasons/<int:year>/",               views.season_detail),
    path("encyclopedia/drivers/",                          views.drivers_list),
    path("encyclopedia/drivers/<str:name>/",               views.driver_detail),
    path("encyclopedia/constructors/",                     views.constructors_list),
    path("encyclopedia/constructors/<str:name>/",          views.constructor_detail),
    path("encyclopedia/circuits/",                         views.circuits_list),
    path("encyclopedia/circuits/<str:name>/",              views.circuit_detail),
    path("encyclopedia/history/",                          views.history_list),
    path("encyclopedia/history/<str:era>/",                views.history_detail),
    path("encyclopedia/champions/",                        views.champions_list),
]
