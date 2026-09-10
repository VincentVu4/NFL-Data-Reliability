import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from validation import validate_games


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
            # print(json.dumps(nfl_data["events"][0], indent=2))
            # print(json.dumps(nfl_data["events"][0]["competitions"][0]["competitors"][0], indent=2))
           
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

def parse_games(raw_nfl_data, retrieved_at):

    games = []

    for event in raw_nfl_data["events"]:                #loops through json file and grabs data for each game
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
        
        games.append(game)

    return games

def parse_play_by_play():
    pass

def parse_odds():
    pass

def run_pipeline():
    retrieved_at = datetime.now(timezone.utc)

    raw_nfl_data = extract_nfl_data()
    raw_file_path = save_raw_response(
        raw_nfl_data,
        retrieved_at
    )

    games = parse_games(raw_nfl_data, retrieved_at)
    valid_games, rejected_games = validate_games(games)

    valid_df = pd.DataFrame(valid_games)
    rejected_df = pd.DataFrame(rejected_games)

    print(f"Raw file: {raw_file_path}")
    print(f"Parsed games: {len(games)}")
    print(f"Valid games: {len(valid_games)}")
    print(f"Rejected games: {len(rejected_games)}")

    print(valid_df.to_string(index=False))

    if not rejected_df.empty:
        print("\nRejected games:")
        print(rejected_df.to_string(index=False))

    return valid_games, rejected_games


if __name__ == "__main__":
    run_pipeline()

if __name__ == "__main__":
    run_pipeline()