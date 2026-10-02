from unittest.mock import Mock

import pytest

from src import adls_storage


def test_upload_file_to_adls(monkeypatch, tmp_path):
    local_file = tmp_path / "snapshot.json"
    local_file.write_text(
        '{"game_id": "123"}',
        encoding="utf-8"
    )

    service_client = Mock()
    file_system_client = Mock()
    directory_client = Mock()
    file_client = Mock()

    service_client.get_file_system_client.return_value = (
        file_system_client
    )

    file_system_client.get_directory_client.return_value = (
        directory_client
    )

    directory_client.exists.return_value = True
    directory_client.get_file_client.return_value = (
        file_client
    )

    monkeypatch.setattr(
        adls_storage,
        "create_data_lake_service_client",
        lambda: service_client
    )

    monkeypatch.setattr(
        adls_storage,
        "AZURE_STORAGE_ACCOUNT_NAME",
        "teststorage"
    )

    monkeypatch.setattr(
        adls_storage,
        "AZURE_STORAGE_FILE_SYSTEM",
        "nfl-data"
    )

    result = adls_storage.upload_file_to_adls(
        local_file,
        remote_directory="landing"
    )

    service_client.get_file_system_client.assert_called_once_with(
        "nfl-data"
    )

    directory_client.get_file_client.assert_called_once_with(
        "snapshot.json"
    )

    file_client.create_file.assert_called_once_with(
        if_none_match="*"
    )

    append_arguments = file_client.append_data.call_args.kwargs

    assert append_arguments["offset"] == 0
    assert append_arguments["length"] == local_file.stat().st_size

    file_client.flush_data.assert_called_once_with(
        offset=local_file.stat().st_size
    )

    assert result == (
        "abfss://nfl-data@teststorage."
        "dfs.core.windows.net/landing/snapshot.json"
    )


def test_upload_rejects_missing_local_file(tmp_path):
    missing_file = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        adls_storage.upload_file_to_adls(
            missing_file
        )