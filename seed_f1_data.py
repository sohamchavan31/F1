"""
Seed MongoDB with F1 encyclopedia data.

Run once (idempotent — upserts by natural key):
    python seed_f1_data.py
"""

import logging
from engine.storage import get_db
from engine.encyclopedia import SEASONS, DRIVERS, CONSTRUCTORS, CIRCUITS, HISTORY

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def seed_collection(db, collection_name: str, docs: list, key_fields: list[str]):
    col = db[collection_name]
    upserted = inserted = 0
    for doc in docs:
        key = {f: doc[f] for f in key_fields}
        result = col.update_one(key, {"$set": doc}, upsert=True)
        if result.upserted_id:
            inserted += 1
        else:
            upserted += 1
    log.info(f"  {collection_name}: {inserted} inserted, {upserted} updated  ({len(docs)} total)")


def ensure_encyclopedia_indexes(db):
    db.f1_seasons.create_index("year", unique=True, name="season_year")
    db.f1_drivers.create_index("name", unique=True, name="driver_name")
    db.f1_constructors.create_index("name", unique=True, name="constructor_name")
    db.f1_circuits.create_index("name", unique=True, name="circuit_name")
    db.f1_history.create_index("era", unique=True, name="history_era")
    log.info("Encyclopedia indexes OK")


def main():
    log.info("Seeding F1 encyclopedia data ...")
    db = get_db()
    ensure_encyclopedia_indexes(db)

    seed_collection(db, "f1_seasons",      SEASONS,      ["year"])
    seed_collection(db, "f1_drivers",      DRIVERS,      ["name"])
    seed_collection(db, "f1_constructors", CONSTRUCTORS, ["name"])
    seed_collection(db, "f1_circuits",     CIRCUITS,     ["name"])
    seed_collection(db, "f1_history",      HISTORY,      ["era"])

    log.info("Done.")
    log.info(f"  f1_seasons:      {db.f1_seasons.count_documents({})}")
    log.info(f"  f1_drivers:      {db.f1_drivers.count_documents({})}")
    log.info(f"  f1_constructors: {db.f1_constructors.count_documents({})}")
    log.info(f"  f1_circuits:     {db.f1_circuits.count_documents({})}")
    log.info(f"  f1_history:      {db.f1_history.count_documents({})}")


if __name__ == "__main__":
    main()
