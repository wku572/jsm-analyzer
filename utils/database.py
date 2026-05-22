from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime
import pytz


DB_DIR = Path("data")
DB_FILE = DB_DIR / "jsm_analyzer.db"

CURRENT_TABLE = "current_snapshot"
HISTORY_TABLE = "historical_snapshots"

LOCAL_TZ = "Africa/Addis_Ababa"


def get_connection():
    DB_DIR.mkdir(exist_ok=True)
    return sqlite3.connect(DB_FILE)


def get_snapshot_timestamp():
    tz = pytz.timezone(LOCAL_TZ)

    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def save_current_snapshot(df):

    with get_connection() as conn:

        df.to_sql(
            CURRENT_TABLE,
            conn,
            if_exists="replace",
            index=False
        )


def save_historical_snapshot(df):

    snapshot_df = df.copy()

    snapshot_df["snapshot_timestamp"] = get_snapshot_timestamp()

    with get_connection() as conn:

        snapshot_df.to_sql(
            HISTORY_TABLE,
            conn,
            if_exists="append",
            index=False
        )


def load_current_snapshot():

    if not DB_FILE.exists():
        return None

    with get_connection() as conn:

        try:
            return pd.read_sql_query(
                f"SELECT * FROM {CURRENT_TABLE}",
                conn
            )

        except Exception:
            return None


def load_historical_snapshots():

    if not DB_FILE.exists():
        return None

    with get_connection() as conn:

        try:
            return pd.read_sql_query(
                f"SELECT * FROM {HISTORY_TABLE}",
                conn
            )

        except Exception:
            return None


def clear_current_snapshot():

    if not DB_FILE.exists():
        return

    with get_connection() as conn:

        conn.execute(
            f"DROP TABLE IF EXISTS {CURRENT_TABLE}"
        )

        conn.commit()


def clear_historical_snapshots():

    if not DB_FILE.exists():
        return

    with get_connection() as conn:

        conn.execute(
            f"DROP TABLE IF EXISTS {HISTORY_TABLE}"
        )

        conn.commit()