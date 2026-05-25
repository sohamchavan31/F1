# F1 Race Replay Engine

## Project Structure

```
f1_replay/                    ← project root
├── engine/
│   ├── __init__.py
│   ├── loader.py             # FastF1 session download + driver metadata
│   ├── timeline.py           # Timeline sync — aligns all 20 cars to shared ms clock
│   └── storage.py            # MongoDB read/write (sessions, frames, track_maps)
├── tests/
│   └── test_pipeline.py      # Offline test (no MongoDB needed)
├── f1_django/                # Phase 2 — Django + Channels backend
│   ├── manage.py
│   ├── requirements.txt
│   ├── f1_project/
│   │   ├── settings.py       # CHANNEL_LAYERS with Redis
│   │   ├── urls.py
│   │   └── asgi.py
│   └── api/
│       ├── views.py          # DRF: list sessions, get track map, frame seek
│       ├── consumers.py      # Django Channels WebSocket: stream frames
│       ├── routing.py        # WebSocket URL routing
│       ├── urls.py
│       └── db.py             # Async Motor client
├── data_cache/               # FastF1 auto-cache (created on first run)
├── load_race.py              # CLI entry point — load race into MongoDB
└── README.md
```

---

## Phase 1 — Telemetry Engine

### Setup

```bash
pip install fastf1 pymongo motor numpy pandas
```

MongoDB — run locally via Docker:
```bash
docker run -d -p 27017:27017 --name f1mongo mongo:7
```

### Usage

**Test without MongoDB (validates pipeline)**
```bash
python tests/test_pipeline.py
```
Downloads 2023 Monza data (~50 MB on first run, cached after).

**Load a full race into MongoDB**
```bash
# Full race (~20 min processing, ~500k frames for a 90-min race)
python load_race.py --year 2024 --event Monaco --session Race

# Quick test — first 300 frames only
python load_race.py --year 2023 --event Monza --session Race --test
```

### Available events (FastF1 names)
Bahrain, Saudi Arabia, Australia, Japan, China, Miami, Imola, Monaco,
Canada, Spain, Austria, British, Hungary, Belgian, Dutch, Italian,
Singapore, United States, Mexico City, São Paulo, Las Vegas, Qatar, Abu Dhabi

### MongoDB Collections

**`sessions`**
```json
{
  "_id": "...",
  "year": 2024,
  "event": "Monaco",
  "session_type": "Race",
  "total_laps": 78,
  "drivers": [
    { "code": "LEC", "full_name": "Charles Leclerc", "team": "Ferrari",
      "color": "#E8002D", "number": 16 }
  ],
  "track_bounds": { "x_min": -1200, "x_max": 900, "y_min": -800, "y_max": 600 }
}
```

**`frames`**
```json
{
  "session_id": "...",
  "t": 12400,
  "cars": {
    "LEC": { "x": 0.412, "y": 0.288, "speed": 187, "throttle": 72,
             "brake": false, "gear": 5, "drs": false, "lap": 3, "pos": 1 },
    "VER": { "..." }
  }
}
```

**`track_maps`**
```json
{
  "event": "Monaco",
  "year": 2024,
  "points": [{ "x": 0.42, "y": 0.31 }, "..."],
  "n_points": 847
}
```

### Environment Variables

| Variable    | Default                   | Description        |
|-------------|---------------------------|--------------------|
| MONGO_URI   | mongodb://localhost:27017 | MongoDB connection |
| F1_DB_NAME  | f1_replay                 | Database name      |

---

## Phase 2 — Django + Channels Backend

### Additional setup

```bash
# Redis (required for Django Channels channel layer)
docker run -d -p 6379:6379 --name f1redis redis:7

cd f1_django
pip install -r requirements.txt
```

### Run

```bash
cd f1_django
uvicorn f1_project.asgi:application --host 0.0.0.0 --port 8000 --reload
```

### REST API

| Method | Endpoint                              | Description                         |
|--------|---------------------------------------|-------------------------------------|
| GET    | `/api/sessions/`                      | List all loaded sessions            |
| GET    | `/api/sessions/<session_id>/`         | Session detail + driver list        |
| GET    | `/api/track-map/<event>/`             | Track SVG points (latest year)      |
| GET    | `/api/track-map/<event>/<year>/`      | Track SVG points for specific year  |
| GET    | `/api/frame/<session_id>/<t_ms>/`     | Nearest frame at timestamp `t_ms`   |

### WebSocket

Connect to:
```
ws://localhost:8000/ws/replay/<session_id>/
```

**Client → Server messages:**
```json
{ "action": "play",   "session_id": "<id>", "t_start": 0,    "speed": 1.0 }
{ "action": "pause" }
{ "action": "resume" }
{ "action": "seek",   "t": 45000 }
{ "action": "speed",  "speed": 2.0 }
```

**Server → Client messages:**
```json
{ "type": "frame",  "t": 12400, "cars": { "LEC": { ... }, "VER": { ... } } }
{ "type": "status", "state": "playing", "t": 12400, "speed": 1.0 }
{ "type": "error",  "message": "..." }
```

### Additional Environment Variables

| Variable      | Default                   | Description             |
|---------------|---------------------------|-------------------------|
| REDIS_URL     | redis://localhost:6379    | Redis for Channels      |
| DJANGO_SECRET_KEY | (dev key)             | Set in production       |
| DEBUG         | 1                         | Set to 0 in production  |
| ALLOWED_HOSTS | localhost 127.0.0.1       | Space-separated hosts   |
