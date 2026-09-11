import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import hashlib
import pandas as pd
import requests

from src.validation import validate_games

logger = logging.getLogger(__name__)


def extract_nfl_data(max_attempts=3):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                timeout=30
            )

            response.raise_for_status()
            raw_nfl_data = response.json()
           
            return raw_nfl_data

        except requests.RequestException as error:
            logger.warning(
                "API attempt %s of %s failed: %s",
                attempt,
                max_attempts,
                error
            )

            if attempt == max_attempts:
                raise

            time.sleep(2)

def save_raw_response(nfl_data, retrieved_at):
    raw_directory = Path("data/raw")
    raw_directory.mkdir(parents=True, exist_ok=True)

    timestamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    file_path = raw_directory / f"nfl_scoreboard_{timestamp}.json"

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(nfl_data, file, indent=2)

    logger.info("Raw response saved to %s", file_path)

    return file_path

def save_quarantined_games(rejected_games, retrieved_at):       # Rejected nfl games saved to this path
    if not rejected_games:
        logger.info("No rejected games to quarantine")
        return None

    quarantine_directory = Path("data/quarantine")
    quarantine_directory.mkdir(parents=True, exist_ok=True)

    timestamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    file_path = (
        quarantine_directory
        / f"rejected_games_{timestamp}.json"
    )

    quarantine_output = {
        "retrieved_at": retrieved_at.isoformat(),
        "source": "ESPN",
        "rejected_record_count": len(rejected_games),
        "records": rejected_games
    }

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(quarantine_output, file, indent=2)

    logger.warning(
        "%s rejected games saved to %s",
        len(rejected_games),
        file_path
    )

    return file_path

def calculate_game_hash(game):
    tracked_fields = {
        "game_id": game["game_id"],
        "scheduled_at": game["scheduled_at"],
        "game_state": game["game_state"],
        "status_name": game["status_name"],
        "status_detail": game["status_detail"],
        "completed": game["completed"],
        "period": game["period"],
        "clock": game["clock"],
        "home_score": game["home_score"],
        "away_score": game["away_score"]
    }

    serialized_game = json.dumps(
        tracked_fields,
        sort_keys=True
    )

    return hashlib.sha256(
        serialized_game.encode("utf-8")
    ).hexdigest()

def parse_games(raw_nfl_data, retrieved_at):
    parsed_games = []
    parsing_rejections = []

    for event in raw_nfl_data["events"]:                #loops through json file and grabs data for each game
        try:
            competition = event["competitions"][0]
            competitors = competition["competitors"]
            status = competition["status"]
            status_type = status["type"]
            venue = competition.get("venue", {})

            home_team = next(
                    team
                    for team in competitors
                    if team["homeAway"] == "home"
                )

            away_team = next(
                team
                for team in competitors
                if team["homeAway"] == "away"
            )
            game = {
                "game_id": event["id"],
                "scheduled_at": event["date"],
                "season": event["season"]["year"],
                "season_type": event["season"]["slug"],
                "week": event["week"]["number"],

                "game_state": status_type["state"],
                "status_name": status_type["name"],
                "status_detail": status_type["detail"],
                "completed": status_type["completed"],
                "period": status["period"],
                "clock": status["displayClock"],

                "home_team_id": home_team["team"]["id"],
                "home_team_name": home_team["team"]["displayName"],
                "home_score": int(home_team["score"]),

                "away_team_id": away_team["team"]["id"],
                "away_team_name": away_team["team"]["displayName"],
                "away_score": int(away_team["score"]),

                "venue_id": venue.get("id"),
                "venue_name": venue.get("fullName"),

                "retrieved_at": retrieved_at.isoformat(),
                "source": "ESPN"
            }
            game["record_hash"] = calculate_game_hash(game)

            parsed_games.append(game)
        except (
            KeyError,
            IndexError,
            StopIteration,
            TypeError,
            ValueError
        ) as error:
            parsing_rejections.append({
                "game_id": event.get("id"),
                "retrieved_at": retrieved_at.isoformat(),
                "source": "ESPN",
                "rejection_stage": "parsing",
                "rejection_reason": (
                    f"{type(error).__name__}: {error}"
                ),
                "raw_record": event
            })
        
    # games[1]["home_score"] = -3    #Fail case
    return parsed_games, parsing_rejections

def save_processed_games(valid_games, retrieved_at):
    if not valid_games:
        logger.warning("No valid games to save")
        return None

    processed_directory = Path("data/processed")
    processed_directory.mkdir(parents=True, exist_ok=True)

    timestamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    file_path = (
        processed_directory
        / f"nfl_games_{timestamp}.parquet"
    )

    games_df = pd.DataFrame(valid_games)

    games_df["scheduled_at"] = pd.to_datetime(
        games_df["scheduled_at"],
        utc=True,
        errors="coerce"
    )

    games_df["retrieved_at"] = pd.to_datetime(
        games_df["retrieved_at"],
        utc=True,
        errors="coerce"
    )

    games_df.to_parquet(
        file_path,
        index=False,
        engine="pyarrow"
    )

    logger.info(
        "%s valid games saved to %s",
        len(valid_games),
        file_path
    )

    return file_path

def save_pipeline_audit(audit_record):      # Stores record for each run: Succeeded/Duration/Num of passed failed
    audit_directory = Path("data/audit")
    audit_directory.mkdir(parents=True, exist_ok=True)

    file_path = audit_directory / "pipeline_runs.jsonl"

    with file_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(audit_record) + "\n")

    return file_path

def parse_play_by_play():
    pass

def parse_odds():
    pass

def run_pipeline():
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    start_timer = time.perf_counter()

    source_record_count = 0
    parsed_count = 0
    valid_count = 0
    parsing_rejection_count = 0
    validation_rejection_count = 0

    raw_file_path = None
    processed_file_path = None
    quarantine_file_path = None
    pipeline_status = "FAILED"
    error_message = None

    try:
        raw_nfl_data = extract_nfl_data()

        source_record_count = len(
            raw_nfl_data.get("events", [])
        )

        raw_file_path = save_raw_response(
            raw_nfl_data,
            started_at
        )

        games, parsing_rejections = parse_games(
            raw_nfl_data,
            started_at
        )

        valid_games, validation_rejections = validate_games(
            games
        )

        all_rejected_games = (
            parsing_rejections + validation_rejections
        )

        processed_file_path = save_processed_games(
            valid_games,
            started_at
        )

        quarantine_file_path = save_quarantined_games(
            all_rejected_games,
            started_at
        )

        parsed_count = len(games)
        valid_count = len(valid_games)
        parsing_rejection_count = len(parsing_rejections)
        validation_rejection_count = len(validation_rejections)

        if all_rejected_games:
            pipeline_status = "SUCCESS_WITH_REJECTIONS"
        else:
            pipeline_status = "SUCCESS"

        return valid_games, all_rejected_games

    except Exception as error:
        error_message = f"{type(error).__name__}: {error}"

        logger.exception(
            "Pipeline run %s failed",
            run_id
        )

        raise

    finally:
        finished_at = datetime.now(timezone.utc)

        duration_ms = round(
            (time.perf_counter() - start_timer) * 1000,
            2
        )

        audit_record = {
            "run_id": run_id,
            "pipeline_name": "nfl_scoreboard_pipeline",
            "source": "ESPN",
            "status": pipeline_status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "source_record_count": source_record_count,
            "parsed_count": parsed_count,
            "valid_count": valid_count,
            "parsing_rejection_count": (
                parsing_rejection_count
            ),
            "validation_rejection_count": (
                validation_rejection_count
            ),
            "total_rejection_count": (
                parsing_rejection_count
                + validation_rejection_count
            ),
            "raw_file_path": (
                str(raw_file_path)
                if raw_file_path else None
            ),
            "processed_file_path": (
                str(processed_file_path)
                if processed_file_path else None
            ),
            "quarantine_file_path": (
                str(quarantine_file_path)
                if quarantine_file_path else None
            ),
            "error_message": error_message
        }

        audit_file_path = save_pipeline_audit(audit_record)

        print(f"Pipeline status: {pipeline_status}")
        print(f"Run ID: {run_id}")
        print(f"Duration: {duration_ms} ms")
        print(f"Audit file: {audit_file_path}")


if __name__ == "__main__":
    run_pipeline()
