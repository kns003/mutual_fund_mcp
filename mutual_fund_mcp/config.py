from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("MFAPI_BASE_URL", "https://api.mfapi.in")
    # Horizon's application directory is read-only at runtime; /tmp is writable.
    # Override CACHE_DB_PATH when a persistent writable volume is available.
    db_path: Path = Path(os.getenv("CACHE_DB_PATH", "/tmp/mutual_fund.db"))
    ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "24"))
    risk_free_rate: float = float(os.getenv("RISK_FREE_RATE", "0.06"))

settings = Settings()
