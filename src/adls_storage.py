import logging
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient

from src.config import (
    AZURE_LANDING_DIRECTORY,
    AZURE_STORAGE_ACCOUNT_NAME,
    AZURE_STORAGE_FILE_SYSTEM,
)


logger = logging.getLogger(__name__)


def create_data_lake_service_client():
    if not AZURE_STORAGE_ACCOUNT_NAME:
        raise ValueError(
            "AZURE_STORAGE_ACCOUNT_NAME is not configured"
        )

    account_url = (
        f"https://{AZURE_STORAGE_ACCOUNT_NAME}"
        ".dfs.core.windows.net"
    )

    credential = DefaultAzureCredential()

    return DataLakeServiceClient(
        account_url=account_url,
        credential=credential
    )


def upload_file_to_adls(
    local_file_path,
    remote_directory=AZURE_LANDING_DIRECTORY
):
    local_file_path = Path(local_file_path)

    if not local_file_path.is_file():
        raise FileNotFoundError(
            f"Local file does not exist: {local_file_path}"
        )

    service_client = create_data_lake_service_client()

    file_system_client = (
        service_client.get_file_system_client(
            AZURE_STORAGE_FILE_SYSTEM
        )
    )

    directory_name = remote_directory.strip("/")

    directory_client = (
        file_system_client.get_directory_client(
            directory_name
        )
    )

    if not directory_client.exists():
        directory_client.create_directory()

    file_client = directory_client.get_file_client(
        local_file_path.name
    )

    # Prevent an existing raw snapshot from being overwritten.
    file_client.create_file(
        if_none_match="*"
    )

    file_size = local_file_path.stat().st_size

    with local_file_path.open("rb") as local_file:
        file_client.append_data(
            data=local_file,
            offset=0,
            length=file_size
        )

    file_client.flush_data(
        offset=file_size
    )

    remote_file_path = (
        f"{directory_name}/{local_file_path.name}"
    )

    adls_uri = (
        f"abfss://{AZURE_STORAGE_FILE_SYSTEM}@"
        f"{AZURE_STORAGE_ACCOUNT_NAME}"
        f".dfs.core.windows.net/{remote_file_path}"
    )

    logger.info(
        "Uploaded %s to %s",
        local_file_path,
        adls_uri
    )

    return adls_uri