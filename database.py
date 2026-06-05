import sqlite3
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "linkedin_profiles.db"


def init_db(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS linkedin_profiles (
                id              INTEGER PRIMARY KEY,
                linkedin_url    TEXT UNIQUE,
                full_name       TEXT,
                headline        TEXT,
                location        TEXT,
                current_company TEXT,
                about_text      TEXT,
                experience_json TEXT,
                education_json  TEXT,
                collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    logger.info("DB initialised at %s", db_path)


def insert_profile(profile: dict, db_path: str = DB_PATH) -> bool:
    sql = """
        INSERT OR IGNORE INTO linkedin_profiles
            (linkedin_url, full_name, headline, location, current_company,
             about_text, experience_json, education_json)
        VALUES
            (:linkedin_url, :full_name, :headline, :location, :current_company,
             :about_text, :experience_json, :education_json)
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(sql, profile)
        conn.commit()
        inserted = cursor.rowcount == 1
    if inserted:
        logger.debug("Inserted profile: %s", profile.get("linkedin_url"))
    else:
        logger.debug("Duplicate ignored: %s", profile.get("linkedin_url"))
    return inserted


def insert_profile_batch(profiles: list, db_path: str = DB_PATH) -> int:
    """Batch insert profiles into database. Returns count of inserted profiles."""
    count = 0
    for profile in profiles:
        if insert_profile(profile, db_path):
            count += 1
    logger.info(f"Batch insert complete: {count}/{len(profiles)} profiles inserted")
    return count


def get_profiles_df(db_path: str = DB_PATH) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM linkedin_profiles", conn)
    logger.debug("Loaded %d profiles from %s", len(df), db_path)
    return df


if __name__ == "__main__":
    import json, tempfile, os
    tmp = tempfile.mktemp(suffix=".db")
    try:
        init_db(tmp)
        sample = {
            "linkedin_url": "https://www.linkedin.com/in/testuser",
            "full_name": "Test User",
            "headline": "Software Engineer",
            "location": "London, UK",
            "current_company": "Acme Corp",
            "about_text": "Builder of things.",
            "experience_json": json.dumps([{"title": "SWE", "company": "Acme"}]),
            "education_json": json.dumps([{"school": "MIT", "degree": "BS CS"}]),
        }
        r1 = insert_profile(sample, tmp)
        r2 = insert_profile(sample, tmp)      # duplicate → should return False
        df = get_profiles_df(tmp)
        assert r1 is True, "First insert must return True"
        assert r2 is False, "Duplicate insert must return False"
        assert len(df) == 1, "Table must contain exactly 1 row"
        print("All assertions passed. DB layer functional.")
        print(df.to_string())
    finally:
        os.unlink(tmp)
