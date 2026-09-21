def validate_games(games):
    valid_games = []
    rejected_games = []

    for game in games:
        rejection_reasons = []

        if not game.get("game_id"):
            rejection_reasons.append("Missing game_id")

        if not game.get("scheduled_at"):
            rejection_reasons.append("Missing scheduled_at")

        if not isinstance(game.get("season"), int):
            rejection_reasons.append("Invalid season")

        if not isinstance(game.get("week"), int):
            rejection_reasons.append("Invalid week")

        if not game.get("home_team_id"):
            rejection_reasons.append("Missing home_team_id")

        if not game.get("away_team_id"):
            rejection_reasons.append("Missing away_team_id")

        if game.get("home_team_id") == game.get("away_team_id"):
            rejection_reasons.append("Home and away teams are identical")

        if not isinstance(game.get("home_score"), int):
            rejection_reasons.append("Invalid home_score")
        elif game["home_score"] < 0:
            rejection_reasons.append("Negative home_score")

        if not isinstance(game.get("away_score"), int):
            rejection_reasons.append("Invalid away_score")
        elif game["away_score"] < 0:
            rejection_reasons.append("Negative away_score")

        if game.get("game_state") not in {"pre", "in", "post"}:
            rejection_reasons.append("Invalid game_state")

        if rejection_reasons:
            rejected_game = {
                **game,
                "rejection_reason": "; ".join(rejection_reasons)
            }
            rejected_games.append(rejected_game)
        else:
            valid_games.append(game)
    
    return valid_games, rejected_games

def run_tests():
    pass


