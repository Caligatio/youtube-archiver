from enum import Enum, auto
from pathlib import Path
from typing import Literal, NamedTuple, TypedDict


class UpdateStatusCode(Enum):
    """Enum for the various update message status values."""

    COMPLETED = auto()
    DELETED = auto()
    DOWNLOADED = auto()
    DOWNLOADING = auto()
    ERROR = auto()


class DownloadResult(NamedTuple):
    """Tuple containing all possible outputs from a download request."""

    pretty_name: str
    key: str
    info_file: Path
    video_file: Path | None
    audio_file: Path | None


class DeletedUpdate(TypedDict):
    """Realtime update message indicating a key was deleted."""

    status: Literal[UpdateStatusCode.DELETED]
    key: str | None


class _ErrorUpdateNoReqID(TypedDict):
    """Realtime update message indicating an error was encountered."""

    status: Literal[UpdateStatusCode.ERROR]
    msg: str


class ErrorUpdate(_ErrorUpdateNoReqID, total=False):
    """Realtime update message indicating an error was encountered, with optional `req_id`."""

    req_id: str


class _DownloadedUpdateNoReqID(TypedDict):
    """Realtime update message indicating a file was downloaded."""

    status: Literal[UpdateStatusCode.DOWNLOADED]
    filename: Path


class DownloadedUpdate(_DownloadedUpdateNoReqID, total=False):
    """Realtime update message indicating a file was downloaded, with optional `req_id`."""

    req_id: str


class _DownloadingUpdateNoReqID(TypedDict):
    """Realtime update message indicating a file is downloading."""

    status: Literal[UpdateStatusCode.DOWNLOADING]
    filename: Path
    downloaded_bytes: int
    total_bytes: int | None


class DownloadingUpdate(_DownloadingUpdateNoReqID, total=False):
    """Realtime update message indicating a file is downloading, with optional `req_id`."""

    req_id: str


class _CompletedUpdateNoReqID(TypedDict):
    """Realtime update message indicating a download request was completed."""

    status: Literal[UpdateStatusCode.COMPLETED]
    pretty_name: str
    key: str
    path: Path
    info_file: Path
    video_file: Path | None
    audio_file: Path | None


class CompletedUpdate(_CompletedUpdateNoReqID, total=False):
    """Realtime update message indicating a download request was completed, with optional `req_id`."""

    req_id: str


# Type that contains all possible realtime update message types
UpdateMessage = DeletedUpdate | DownloadedUpdate | DownloadingUpdate | CompletedUpdate | ErrorUpdate
