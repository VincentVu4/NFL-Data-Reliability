import logging
from datetime import datetime, timezone

from src.adls_storage import upload_file_to_adls
from src.config import ENABLE_ADLS_UPLOAD
from src.pipeline import (
    extract_nfl_data,
    save_raw_response,
)


logger = logging.getLogger(__name__)


def backfill_regular_season(
    season,
    start_week,
    end_week
):
    if start_week < 1:
        raise ValueError(
            "start_week must be at least 1"
        )

    if end_week > 18:
        raise ValueError(
            "end_week cannot exceed 18"
        )

    if start_week > end_week:
        raise ValueError(
            "start_week cannot exceed end_week"
        )

    saved_files = []

    for week in range(
        start_week,
        end_week + 1
    ):
        logger.info(
            "Backfilling season=%s week=%s",
            season,
            week
        )

        retrieved_at = datetime.now(
            timezone.utc
        )

        nfl_data = extract_nfl_data(
            season=season,
            season_type=2,
            week=week
        )

        event_count = len(
            nfl_data.get("events", [])
        )

        raw_file_path = save_raw_response(
            nfl_data=nfl_data,
            retrieved_at=retrieved_at,
            season=season,
            season_type=2,
            week=week
        )

        adls_uri = None

        if ENABLE_ADLS_UPLOAD:
            adls_uri = upload_file_to_adls(
                raw_file_path
            )

        saved_files.append(
            {
                "season": season,
                "week": week,
                "event_count": event_count,
                "local_file": str(raw_file_path),
                "adls_uri": adls_uri
            }
        )

        print(
            f"Week {week}: "
            f"{event_count} events saved to "
            f"{raw_file_path}"
        )

        if adls_uri:
            print(
                f"Week {week} uploaded to "
                f"{adls_uri}"
            )

    return saved_files


if __name__ == "__main__":
    backfill_regular_season(
        season=2026,
        start_week=1,
        end_week=3
    )