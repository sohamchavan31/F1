"""
DRF views for the F1 Replay API.

Replay endpoints
----------------
GET  /api/sessions/                    → list all sessions
GET  /api/sessions/<session_id>/       → single session detail
GET  /api/track-map/<event>/           → track map points
GET  /api/track-map/<event>/<year>/    → track map for a specific year
GET  /api/frame/<session_id>/<t_ms>/   → nearest frame at timestamp t_ms

Encyclopedia endpoints
----------------------
GET  /api/encyclopedia/seasons/                → all seasons 1950–present
GET  /api/encyclopedia/seasons/<year>/         → single season
GET  /api/encyclopedia/drivers/                → all drivers
GET  /api/encyclopedia/drivers/<name>/         → single driver
GET  /api/encyclopedia/constructors/           → all constructors
GET  /api/encyclopedia/constructors/<name>/    → single constructor
GET  /api/encyclopedia/circuits/               → all circuits
GET  /api/encyclopedia/circuits/<name>/        → single circuit
GET  /api/encyclopedia/history/                → full history timeline
GET  /api/encyclopedia/history/<era>/          → single era
GET  /api/encyclopedia/champions/              → driver champions by year (quick lookup)
"""

import os
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient, ASCENDING
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


def _get_db():
    uri  = os.getenv("MONGO_URI",  "mongodb://localhost:27017")
    name = os.getenv("F1_DB_NAME", "f1_replay")
    return MongoClient(uri, serverSelectionTimeoutMS=3000)[name]


def _serialize_doc(doc: dict) -> dict:
    """Replace ObjectId with str so DRF can JSON-serialize."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Sessions ──────────────────────────────────────────────────────────────────

@api_view(["GET"])
def session_list(request):
    """List all loaded sessions, sorted newest first. Drivers included."""
    db = _get_db()
    docs = list(db.sessions.find({}).sort("year", -1))
    return Response([_serialize_doc(d) for d in docs])


@api_view(["GET"])
def session_detail(request, session_id: str):
    """Full session document including driver list."""
    try:
        oid = ObjectId(session_id)
    except InvalidId:
        return Response({"error": "invalid session_id"}, status=status.HTTP_400_BAD_REQUEST)

    db  = _get_db()
    doc = db.sessions.find_one({"_id": oid})
    if not doc:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(_serialize_doc(doc))


# ── Track map ─────────────────────────────────────────────────────────────────

@api_view(["GET"])
def track_map(request, event: str, year: int = None):
    """
    Return the SVG polyline points for a circuit.
    If year is omitted, returns the most recently loaded version.
    """
    db    = _get_db()
    query = {"event": event}
    if year:
        query["year"] = year
    doc = db.track_maps.find_one(query, {"_id": 0}, sort=[("year", -1)])
    if not doc:
        return Response({"error": "track map not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


# ── Frame lookup ──────────────────────────────────────────────────────────────

@api_view(["GET"])
def frame_at(request, session_id: str, t_ms: int):
    """
    Return the nearest frame at or before t_ms for the given session.
    Used by the React client for initial seek / scrubbing.
    """
    db  = _get_db()
    doc = db.frames.find_one(
        {"session_id": session_id, "t": {"$lte": t_ms}},
        {"_id": 0},
        sort=[("t", -1)],
    )
    if not doc:
        return Response({"error": "no frame found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


# ── Encyclopedia ──────────────────────────────────────────────────────────────

@api_view(["GET"])
def seasons_list(request):
    db   = _get_db()
    docs = list(db.f1_seasons.find({}, {"_id": 0}).sort("year", 1))
    return Response(docs)


@api_view(["GET"])
def season_detail(request, year: int):
    db  = _get_db()
    doc = db.f1_seasons.find_one({"year": year}, {"_id": 0})
    if not doc:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


@api_view(["GET"])
def drivers_list(request):
    db   = _get_db()
    docs = list(db.f1_drivers.find({}, {"_id": 0}).sort("championships", -1))
    return Response(docs)


@api_view(["GET"])
def driver_detail(request, name: str):
    db  = _get_db()
    doc = db.f1_drivers.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}, {"_id": 0})
    if not doc:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


@api_view(["GET"])
def constructors_list(request):
    db   = _get_db()
    docs = list(db.f1_constructors.find({}, {"_id": 0}).sort("constructor_titles", -1))
    return Response(docs)


@api_view(["GET"])
def constructor_detail(request, name: str):
    db  = _get_db()
    doc = db.f1_constructors.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}, {"_id": 0})
    if not doc:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


@api_view(["GET"])
def circuits_list(request):
    db   = _get_db()
    docs = list(db.f1_circuits.find({}, {"_id": 0}).sort("first_gp", 1))
    return Response(docs)


@api_view(["GET"])
def circuit_detail(request, name: str):
    db  = _get_db()
    doc = db.f1_circuits.find_one({"name": {"$regex": name, "$options": "i"}}, {"_id": 0})
    if not doc:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


@api_view(["GET"])
def history_list(request):
    db   = _get_db()
    docs = list(db.f1_history.find({}, {"_id": 0}))
    return Response(docs)


@api_view(["GET"])
def history_detail(request, era: str):
    db  = _get_db()
    doc = db.f1_history.find_one({"era": {"$regex": era, "$options": "i"}}, {"_id": 0})
    if not doc:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(doc)


@api_view(["GET"])
def champions_list(request):
    """Quick lookup: all driver world champions by year."""
    db   = _get_db()
    docs = list(db.f1_seasons.find({}, {"_id": 0, "year": 1, "driver_champion": 1, "team": 1, "constructor_champion": 1}).sort("year", -1))
    return Response(docs)
