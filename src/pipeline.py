import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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

def classify_game_changes(
    valid_games,
    state_file_path=Path("data/state/latest_games.json")
):
    state_file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if state_file_path.exists():
        with state_file_path.open(
            "r",
            encoding="utf-8"
        ) as file:
            previous_state = json.load(file)
    else:
        previous_state = {}

    updated_state = previous_state.copy()

    for game in valid_games:
        game_id = game["game_id"]
        current_hash = game["record_hash"]

        previous_game = previous_state.get(game_id)
        previous_hash = None

        if previous_game:
            previous_hash = previous_game.get("record_hash")

        if previous_game is None:
            change_type = "NEW"
            last_changed_at = game["retrieved_at"]

        elif previous_hash != current_hash:
            change_type = "CHANGED"
            last_changed_at = game["retrieved_at"]

        else:
            change_type = "UNCHANGED"
            last_changed_at = previous_game.get(
                "last_changed_at",
                game["retrieved_at"]
            )

        game["change_type"] = change_type
        game["previous_record_hash"] = previous_hash
        game["last_changed_at"] = last_changed_at

        updated_state[game_id] = {
            "record_hash": current_hash,
            "last_seen_at": game["retrieved_at"],
            "last_changed_at": last_changed_at
        }

    temporary_path = state_file_path.with_suffix(".tmp")

    with temporary_path.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(updated_state, file, indent=2)

    temporary_path.replace(state_file_path)

    return valid_games

def detect_stale_games(    # detects if a live game hasn't changed
    valid_games,
    stale_threshold_minutes=10
):
    stale_games = []

    for game in valid_games:
        game["reliability_status"] = "HEALTHY"
        game["stale_minutes"] = 0.0
        game["alert_reason"] = None

        if game["game_state"] != "in":
            game["reliability_status"] = "NOT_APPLICABLE"
            continue

        if game["change_type"] != "UNCHANGED":
            continue

        retrieved_at = datetime.fromisoformat(
            game["retrieved_at"]
        )

        last_changed_at = datetime.fromisoformat(
            game["last_changed_at"]
        )

        stale_minutes = (
            retrieved_at - last_changed_at
        ).total_seconds() / 60

        game["stale_minutes"] = round(stale_minutes, 2)

        if stale_minutes >= stale_threshold_minutes:
            game["reliability_status"] = "STALE"
            game["alert_reason"] = (
                f"Live game has not changed for "
                f"{round(stale_minutes, 2)} minutes"
            )

            stale_games.append(game.copy())

    return valid_games, stale_games

def save_reliability_alerts(   # alerts if stale game is detected
    stale_games,
    detected_at,
    alerts_directory=Path("data/alerts")
):
    if not stale_games:
        logger.info("No reliability alerts generated")
        return None

    alerts_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = detected_at.strftime("%Y%m%dT%H%M%SZ")
    file_path = (
        alerts_directory
        / f"reliability_alerts_{timestamp}.json"
    )

    alerts = []

    for game in stale_games:
        incident_key = (
            f"STALE_FEED:"
            f"{game['game_id']}:"
            f"{game['last_changed_at']}"
        )

        alert_id = hashlib.sha256(
            incident_key.encode("utf-8")
        ).hexdigest()

        alert = {
            "alert_id": alert_id,
            "alert_type": "STALE_FEED",
            "severity": "WARNING",
            "source": game["source"],
            "game_id": game["game_id"],
            "home_team_name": game["home_team_name"],
            "away_team_name": game["away_team_name"],
            "game_state": game["game_state"],
            "period": game["period"],
            "clock": game["clock"],
            "home_score": game["home_score"],
            "away_score": game["away_score"],
            "last_changed_at": game["last_changed_at"],
            "detected_at": detected_at.isoformat(),
            "stale_minutes": game["stale_minutes"],
            "alert_reason": game["alert_reason"]
        }

        alerts.append(alert)

    alert_output = {
        "detected_at": detected_at.isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts
    }

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(alert_output, file, indent=2)

    logger.warning(
        "%s reliability alerts saved to %s",
        len(alerts),
        file_path
    )

    return file_path

def calculate_game_hash(game):  # creates a hash to seralize games
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

def parse_games(raw_nfl_data, retrieved_at): #loops through json file and grabs data for each game
    parsed_games = []
    parsing_rejections = []

    for event in raw_nfl_data["events"]:                
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

def configure_logging():
    log_directory = Path("logs")
    log_directory.mkdir(parents=True, exist_ok=True)

    log_file_path = log_directory / "pipeline.log"

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        handlers=[
            logging.FileHandler(
                log_file_path,
                encoding="utf-8"
            ),
            logging.StreamHandler()
        ],
        force=True
    )

    return log_file_path

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
    stale_game_count = 0

    raw_file_path = None
    processed_file_path = None
    quarantine_file_path = None
    alerts_file_path = None
    pipeline_status = "FAILED"
    error_message = None

    logger.info(
    "Starting pipeline run %s",
    run_id
)
    
    try:
        raw_nfl_data = extract_nfl_data()
        
        source_record_count = len(
            raw_nfl_data.get("events", [])
        )
        logger.info(
            "Received %s events from ESPN",
            source_record_count
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

        valid_games = classify_game_changes(valid_games)

        valid_games, stale_games = detect_stale_games(
            valid_games,
            stale_threshold_minutes=10
        )
        alerts_file_path = save_reliability_alerts(
            stale_games,
            started_at
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

        
        
        print(f"Stale game alerts: {len(stale_games)}")
        stale_game_count = len(stale_games)
        parsed_count = len(games)
        valid_count = len(valid_games)
        parsing_rejection_count = len(parsing_rejections)
        validation_rejection_count = len(validation_rejections)

        logger.info(
            "Parsed=%s Valid=%s ParsingRejected=%s "
            "ValidationRejected=%s",
            parsed_count,
            valid_count,
            parsing_rejection_count,
            validation_rejection_count
        )
        logger.info(
            "Detected %s stale live games",
            stale_game_count
        )

        if alerts_file_path:
            print(f"Alerts file: {alerts_file_path}")

        if all_rejected_games:
            pipeline_status = "SUCCESS_WITH_REJECTIONS"
        else:
            pipeline_status = "SUCCESS"
            logger.info(
                "Pipeline run %s completed with status %s",
                run_id,
                pipeline_status
            )
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
            "stale_game_count": stale_game_count,
            "alerts_file_path": (
                str(alerts_file_path)
                if alerts_file_path else None
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
    log_file_path = configure_logging()

    logger.info(
        "Logging initialized at %s",
        log_file_path
    )

    run_pipeline()
