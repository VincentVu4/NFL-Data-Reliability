from src.validation import validate_games


def create_valid_game():
    return {
        "game_id": "401872656",
        "scheduled_at": "2026-09-10T00:20Z",
        "season": 2026,
        "week": 1,
        "game_state": "in",
        "home_team_id": "26",
        "home_team_name": "Seattle Seahawks",
        "home_score": 7,
        "away_team_id": "17",
        "away_team_name": "New England Patriots",
        "away_score": 0
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