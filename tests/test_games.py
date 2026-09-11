from datetime import datetime, timezone

from src.validation import validate_games
from src.pipeline import calculate_game_hash, parse_games

def create_valid_game():
    return {
        "game_id": "401872656",
        "scheduled_at": "2026-09-10T00:20Z",
        "season": 2026,
        "week": 1,
        "game_state": "in",
        "status_name": "STATUS_IN_PROGRESS",
        "status_detail": "7:32 - 2nd Quarter",
        "completed": False,
        "period": 2,
        "clock": "7:32",
        "home_team_id": "26",
        "home_team_name": "Seattle Seahawks",
        "home_score": 7,
        "away_team_id": "17",
        "away_team_name": "New England Patriots",
        "away_score": 7
    }


def test_valid_game_is_accepted():
    game = create_valid_game()

    valid_games, rejected_games = validate_games([game])

    assert len(valid_games) == 1
    assert len(rejected_games) == 0


def test_missing_game_id_is_rejected():
    game = create_valid_game()
    game["game_id"] = None

    valid_games, rejected_games = validate_games([game])

    assert len(valid_games) == 0
    assert len(rejected_games) == 1
    assert "Missing game_id" in rejected_games[0]["rejection_reason"]


def test_negative_score_is_rejected():
    game = create_valid_game()
    game["home_score"] = -3

    valid_games, rejected_games = validate_games([game])

    assert len(valid_games) == 0
    assert len(rejected_games) == 1
    assert "Negative home_score" in rejected_games[0]["rejection_reason"]


def test_multiple_errors_are_recorded():
    game = create_valid_game()
    game["home_score"] = -3
    game["game_state"] = "unknown"

    valid_games, rejected_games = validate_games([game])

    rejection_reason = rejected_games[0]["rejection_reason"]

    assert len(valid_games) == 0
    assert len(rejected_games) == 1
    assert "Negative home_score" in rejection_reason
    assert "Invalid game_state" in rejection_reason


def test_valid_and_invalid_games_are_separated():
    valid_game = create_valid_game()

    invalid_game = create_valid_game()
    invalid_game["game_id"] = "different-game"
    invalid_game["away_score"] = -7

    valid_games, rejected_games = validate_games(
        [valid_game, invalid_game]
    )

    assert len(valid_games) == 1
    assert len(rejected_games) == 1
    assert valid_games[0]["game_id"] == "401872656"
    assert rejected_games[0]["game_id"] == "different-game"

def test_malformed_event_is_quarantined():
    nfl_data = {
        "events": [
            {
                "id": "broken-game"
            }
        ]
    }

    retrieved_at = datetime.now(timezone.utc)

    parsed_games, parsing_rejections = parse_games(
        nfl_data,
        retrieved_at
    )

    assert len(parsed_games) == 0
    assert len(parsing_rejections) == 1
    assert parsing_rejections[0]["game_id"] == "broken-game"
    assert parsing_rejections[0]["rejection_stage"] == "parsing"

def test_identical_game_states_have_same_hash():
    first_game = create_valid_game()
    second_game = create_valid_game()

    first_hash = calculate_game_hash(first_game)
    second_hash = calculate_game_hash(second_game)

    assert first_hash == second_hash

def test_score_change_creates_different_hash():
    first_game = create_valid_game()
    second_game = create_valid_game()

    second_game["home_score"] = 14

    first_hash = calculate_game_hash(first_game)
    second_hash = calculate_game_hash(second_game)

    assert first_hash != second_hash