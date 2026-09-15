import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")


SCOREBOARD_URL = os.getenv(
    "SCOREBOARD_URL",
    (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/football/nfl/scoreboard"
    )
)

MAX_ATTEMPTS = int(
    os.getenv("MAX_ATTEMPTS", "3")
)

REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("REQUEST_TIMEOUT_SECONDS", "30")
)

RETRY_DELAY_SECONDS = float(
    os.getenv("RETRY_DELAY_SECONDS", "2")
)

STALE_THRESHOLD_MINUTES = float(
    os.getenv("STALE_THRESHOLD_MINUTES", "10")
)

DATA_DIRECTORY = Path(
    os.getenv(
        "DATA_DIRECTORY",
        str(PROJECT_ROOT / "data")
    )
)

LOG_DIRECTORY = Path(
    os.getenv(
        "LOG_DIRECTORY",
        str(PROJECT_ROOT / "logs")
    )
)