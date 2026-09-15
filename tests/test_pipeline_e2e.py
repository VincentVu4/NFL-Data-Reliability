import json

import pandas as pd

import src.pipeline as pipeline


def create_mock_espn_response():
    return {
        "events": [
            {
                "id": "test-game-001",
                "date": "2026-09-15T17:00Z",
                "season": {
                    "year": 2026,
                    "slug": "regular-season"
                },
                "week": {
                    "number": 2
                },
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "home",
                                "team": {
                                    "id": "26",
                                    "displayName": "Seattle Seahawks"
                                },
                                "score": "7"
                            },
                            {
                                "homeAway": "away",
                                "team": {
                                    "id": "17",
                                    "displayName": (
                                        "New England Patriots"
                                    )
                                },
                                "score": "3"
                            }
                        ],
                        "status": {
                            "period": 1,
                            "displayClock": "5:32",
                            "type": {
                                "state": "in",
                                "name": "STATUS_IN_PROGRESS",
                                "detail": "5:32 - 1st Quarter",
                                "completed": False
                            }
                        },
                        "venue": {
                            "id": "3673",
                            "fullName": "Test Stadium"
                        }
                    }
                ]
            }
        ]
    }


def test_pipeline_runs_end_to_end(
    tmp_path,
    monkeypatch
):
    temporary_data_directory = tmp_path / "data"

    monkeypatch.setattr(
        pipeline,
        "DATA_DIRECTORY",
        temporary_data_directory
    )

    mock_response = create_mock_espn_response()

    monkeypatch.setattr(
        pipeline,
        "extract_nfl_data",
        lambda: mock_response
    )

    valid_games, rejected_games = pipeline.run_pipeline()

    assert len(valid_games) == 1
    assert len(rejected_games) == 0

    assert valid_games[0]["game_id"] == "test-game-001"
    assert valid_games[0]["home_score"] == 7
    assert valid_games[0]["away_score"] == 3
    assert valid_games[0]["change_type"] == "NEW"

    raw_files = list(
        (temporary_data_directory / "raw").glob("*.json")
    )

    processed_files = list(
        (temporary_data_directory / "processed").glob(
            "*.parquet"
        )
    )

    assert len(raw_files) == 1
    assert len(processed_files) == 1

    processed_df = pd.read_parquet(processed_files[0])

    assert len(processed_df) == 1
    assert processed_df.iloc[0]["game_id"] == (
        "test-game-001"
    )
    assert processed_df.iloc[0]["home_score"] == 7

    state_file = (
        temporary_data_directory
        / "state"
        / "latest_games.json"
    )

    assert state_file.exists()

    audit_file = (
        temporary_data_directory
        / "audit"
        / "pipeline_runs.jsonl"
    )

    assert audit_file.exists()

    with audit_file.open("r", encoding="utf-8") as file:
        audit_records = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    assert len(audit_records) == 1
    assert audit_records[0]["status"] == "SUCCESS"
    assert audit_records[0]["source_record_count"] == 1
    assert audit_records[0]["valid_count"] == 1
    assert audit_records[0]["total_rejection_count"] == 0