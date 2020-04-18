from __future__ import annotations

import json
from functools import partial
from logging import getLogger
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Dict, Optional

from janus import Queue
from youtube_dl import YoutubeDL
from youtube_dl.utils import sanitize_filename

from .custom_types import CompletedUpdate, DownloadedUpdate, DownloadResult, UpdateMessage

logger = getLogger(__name__)
# youtube-dl irritatingly prints log messages if you don't give it a logger
ytdl_logger = getLogger("ytdl")


def process_output_dir(
    download_dir: Path, output_dir: Path, make_title_subdir: bool, download_video: bool, extract_audio: bool
) -> DownloadResult:
    """
    Parses the output from a youtube-dl run and determines which files are the finalized video and/or audio files.

    Moves these from `download_dir` to the specified destination, effectively deleting intermediate files.

    :param download_dir: Directory that contains all the youtube-dl downloaded files
    :param output_dir: Desired output directory
    :param make_title_subdir: Flag indicating whether to create a subdirectory in `output_dir` named after title
    :param download_video: Flag indicating whether video is to be retained
    :param extract_audio: Flag indicating whether audio is to be retained
    :return: Tuple containing information and finalized paths for all the files
    """
    # youtube-dl has a really janky API that returns very little information in terms of what was actually downloaded.
    # We therefore have to make some assumptions:
    #  * If video was requested, the preferred video should be a .mkv file
    #  * If audio was requested, it will be a in .mp3
    #  * If video was requested but the source doesn't support separate bestvideo and bestaudio, the video file will be
    #    whatever file was downloaded (using best)
    # We additionally had to tell youtube-dl to not delete intermediate files if we wanted audio so clear those out.
    leftover_files = {file for file in download_dir.glob("*")}

    info_file = list(download_dir.glob("*.json"))[0]
    leftover_files.remove(info_file)
    with info_file.open() as f_in:
        pretty_name = json.load(f_in)["title"]

    sanitized_title = sanitize_filename(pretty_name)
    if make_title_subdir:
        output_dir = output_dir / sanitized_title
        output_dir.mkdir()

    info_file = info_file.rename(output_dir / f"{sanitized_title}.json")

    audio_file: Optional[Path] = None
    if extract_audio:
        audio_file = list(download_dir.glob("*.mp3"))[0]
        leftover_files.remove(audio_file)
        audio_file = audio_file.rename(output_dir / audio_file.name)

    video_file: Optional[Path] = None
    # Audio identification performed first otherwise the mp3 would be picked as the fallback option if no mkv present
    if download_video:
        try:
            video_file = list(download_dir.glob("*.mkv"))[0]
        except IndexError:
            video_file = list(leftover_files)[0]
            logger.debug("Could not find mkv file, falling back to whatever is present")
        leftover_files.remove(video_file)
        video_file = video_file.rename(output_dir / video_file.name)

    return DownloadResult(pretty_name, output_dir, info_file, video_file, audio_file)


def process_hook(updates_queue: Queue[UpdateMessage], update: Dict[str, str], req_id: Optional[str] = None) -> None:
    """
    A youtube-dl progress callback hook that puts a slightly reformated update into the `update_queue`.

    :param updates_queue: The queue to put the modified update into
    :param update: The received update from youtube-dl
    :param req_id: Optional request ID that is inserted into the status message as "req_id"
    """
    if update["status"] == "finished":
        status_msg: DownloadedUpdate = {"status": "downloaded", "filename": Path(update["filename"])}
        if req_id is not None:
            status_msg["req_id"] = req_id
        updates_queue.sync_q.put_nowait(status_msg)


def download(
    output_dir: Path,
    make_title_subdir: bool,
    url: str,
    download_video: bool,
    extract_audio: bool,
    audio_quality: int = 5,
    updates_queue: Optional[Queue[UpdateMessage]] = None,
    req_id: Optional[str] = None,
    ffmpeg_location: Optional[Path] = None,
) -> DownloadResult:
    """
    Downloads and transcodes (if necessary) a specified online video or audio clip.

    :param output_dir: Desired output directory
    :param make_title_subdir: Flag indicating whether to create a subdirectory in `output_dir` named after title
    :param url: The URL to attempt to download
    :param download_video: Flag indicating that the video should be downloaded
    :param extract_audio: Flag indicating that a separate audio file (MP3) should be created
    :param audio_quality: The MP3 VBR audio quality (1-5)
    :param updates_queue: A queue to put real-time updates into
    :param req_id: An optional ID to include in all `updates-queue` related updates
    :param ffmpeg_location: Path to the directory containing FFMPEG binaries
    :return: Tuple containing information and finalized paths for all the files
    """
    if not output_dir.is_dir():
        raise ValueError("output_dir must be a directory")

    postprocessors = []
    if extract_audio:
        postprocessors.append(
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(audio_quality)}
        )

    progress_hooks = []
    if updates_queue:
        progress_hooks.append(partial(process_hook, updates_queue, req_id=req_id))

    tmp_out = Path(mkdtemp())
    ytdl_opt = {
        "noplaylist": "true",
        "format": "bestvideo+bestaudio/best" if download_video else "bestaudio",
        "outtmpl": str(tmp_out) + "/%(title)s.%(ext)s",
        "progress_hooks": progress_hooks,
        "merge_output_format": "mkv",
        "keepvideo": True if download_video else False,
        "postprocessors": postprocessors,
        "ffmpeg_location": str(ffmpeg_location),
        "logger": ytdl_logger,
    }

    try:
        with YoutubeDL(ytdl_opt) as ytdl:
            info = ytdl.extract_info(url)
            with (tmp_out / "info.json").open("w") as f_out:
                json.dump(info, f_out)

        download_result = process_output_dir(tmp_out, output_dir, make_title_subdir, download_video, extract_audio)
    finally:
        rmtree(tmp_out)

    if updates_queue:
        status_msg: CompletedUpdate = {
            "status": "completed",
            "pretty_name": download_result.pretty_name,
            "info_file": download_result.info_file,
            "video_file": download_result.video_file,
            "audio_file": download_result.audio_file,
        }
        if req_id is not None:
            status_msg["req_id"] = req_id
        updates_queue.sync_q.put_nowait(status_msg)

    return download_result
