import argparse
import logging
import pathlib
from sys import stderr

from .downloader import download
from .server import server


def server_cli() -> int:
    """
    CLI entrypoint to start the API server.

    :return: 0 on success
    """
    parser = argparse.ArgumentParser(description="Backend API server for YouTube Archive")
    parser.add_argument("--port", default=8081, help="TCP port to bind to")
    parser.add_argument("--download-dir", required=True, type=pathlib.Path, help="Path to the download directory")
    parser.add_argument(
        "--downloads-prefix", default="/downloads", help="Path/string to prepend to generated download links"
    )
    parser.add_argument("--ffmpeg-dir", type=pathlib.Path, help="Directory containing FFMPEG")
    parser.add_argument(
        "--logging", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Logging level"
    )

    args = parser.parse_args()

    log_level = getattr(logging, args.logging)
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ytdl_logger = logging.getLogger("ytdl")
    # Things that youtube-dl considers warnings can be squelched
    ytdl_logger.setLevel(level=max(logging.ERROR, log_level))

    server(args.download_dir, args.downloads_prefix, args.port, args.ffmpeg_dir)

    return 0


def download_cli() -> int:
    """
    Quasi-debugging CLI entrypoint that uses youtube-dl to download a video/audio clip.

    :return: 0 on success
    """
    parser = argparse.ArgumentParser(description="Backend API server for YouTube Archive")
    parser.add_argument("url", help="URL to process")
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        default=pathlib.Path.cwd(),
        type=pathlib.Path,
        help="Directory to save the resulting files",
    )
    parser.add_argument("--named-subdir", action="store_true", help="Create a subdirectory based off the URL's title")
    parser.add_argument("--skip-video", action="store_true", help="Do not save video files")
    parser.add_argument("--extract-audio", action="store_true", help="Save audio as a MP3")
    parser.add_argument("--audio-vbr", default=5, type=int, help="MP3 VBR quality")
    parser.add_argument("--ffmpeg-dir", type=pathlib.Path, help="Directory containing FFMPEG")

    args = parser.parse_args()

    if args.skip_video and not args.extract_audio:
        print("You must extract at least video or audio", file=stderr)
        return 1

    download_results = download(
        args.output_dir,
        args.named_subdir,
        args.url,
        not args.skip_video,
        args.extract_audio,
        args.audio_vbr,
        ffmpeg_dir=args.ffmpeg_dir,
    )

    print(f'Successfully processed "{download_results.pretty_name}"')
    print(f"\t Info File: {download_results.info_file}")
    if not args.skip_video:
        print(f"\tVideo File: {download_results.video_file}")
    if args.extract_audio:
        print(f"\tAudio File: {download_results.audio_file}")

    return 0
