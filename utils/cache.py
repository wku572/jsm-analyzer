from pathlib import Path
import pandas as pd


CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "jsm_cached_data.parquet"


def save_cached_data(df):
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_parquet(CACHE_FILE, index=False)


def load_cached_data():
    if CACHE_FILE.exists():
        return pd.read_parquet(CACHE_FILE)
    return None


def clear_cached_data():
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()