"""
Async Motor client — shared across all Django Channels consumers and async views.
Call get_motor_db() to get the database handle.
"""

import os
import motor.motor_asyncio

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None


def get_motor_db():
    global _client
    if _client is None:
        uri  = os.getenv("MONGO_URI",  "mongodb://localhost:27017")
        name = os.getenv("F1_DB_NAME", "f1_replay")
        _client = motor.motor_asyncio.AsyncIOMotorClient(uri)
    return _client[os.getenv("F1_DB_NAME", "f1_replay")]
