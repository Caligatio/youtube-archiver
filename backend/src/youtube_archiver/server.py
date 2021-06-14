from __future__ import annotations

import asyncio
import logging
import pathlib
import shutil
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from json.decoder import JSONDecodeError
from typing import Optional
from uuid import uuid4
from weakref import WeakSet

from aiohttp import WSCloseCode, WSMsgType, web
from janus import Queue

from .custom_types import DownloadResult, UpdateMessage, UpdateStatusCode
from .downloader import AlreadyDownloaded, download

logger = logging.getLogger(__name__)


async def update_publisher(app: web.Application) -> None:
    """
    Background task that listens for downloader updates and publishes them to all connected websockets.

    This function also mangles the contained path names to avoid information leakage.

    :param app: Reference to the overall application.
    """
    try:
        while True:
            update = await app["updates_queue"].async_q.get()
            if update["status"] in [UpdateStatusCode.DOWNLOADING, UpdateStatusCode.DOWNLOADED]:
                # Squash the directory where the file is being downloaded to
                update["filename"] = update["filename"].name
            elif update["status"] == UpdateStatusCode.COMPLETED:
                # Hide the full directory and instead substitute user-accessible path. If download_dir is
                # /var/www/html/downloads, result is in /var/www/html/downloads/Awesome, and download_prefix is
                # "downloads", return /downloads/Awesome
                if update["video_file"]:
                    update["video_file"] = (
                        app["download_prefix"] / update["video_file"].relative_to(app["download_dir"])
                    ).as_posix()
                if update["audio_file"]:
                    update["audio_file"] = (
                        app["download_prefix"] / update["audio_file"].relative_to(app["download_dir"])
                    ).as_posix()
                update["info_file"] = (
                    app["download_prefix"] / update["info_file"].relative_to(app["download_dir"])
                ).as_posix()
                update["path"] = (app["download_prefix"] / update["path"].relative_to(app["download_dir"])).as_posix()

            update["status"] = update["status"].name
            # The websocket updates are best effort, not required.  Don't wait for it to finish
            [asyncio.create_task(ws.send_json(update)) for ws in app["websockets"]]
    except asyncio.CancelledError:
        pass


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    Handler for "status" websockets.  Sends a one-time list of available downloads, :func:`update_publisher` does rest.

    :param request: The incoming (empty) request
    :return: :mod:`aiohttp` mandated response type
    """
    ws = web.WebSocketResponse(heartbeat=5)
    await ws.prepare(request)

    request.app["websockets"].add(ws)

    available_downloads = []
    for child in request.app["download_dir"].iterdir():
        # Directories are made as hobo semaphore, it needs a .json file in it to actually have results.
        if not child.is_dir() or len(list(child.glob("*.json"))) == 0:
            continue

        available_downloads.append(
            {
                "path": (request.app["download_prefix"] / child.relative_to(request.app["download_dir"])).as_posix(),
                "key": child.name,
                "pretty_name": child.name,
            }
        )

    # Sort the downloads in alphabetical order
    available_downloads.sort(key=lambda x: x["pretty_name"])

    await ws.send_json({"downloads": available_downloads, "status": "CONNECTED"})
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == "close":
                    await ws.close()
                    break
            elif msg.type == WSMsgType.PING:
                await ws.pong()
            elif msg.type in [WSMsgType.CLOSED, WSMsgType.ERROR]:
                break
    finally:
        request.app["websockets"].discard(ws)

    return ws


def download_future_handler(
    updates_queue: Queue[UpdateMessage], req_id: str, future: asyncio.Future[DownloadResult]
) -> None:
    """
    Filters out `AlreadyDownloaded` from executor calls to `download`.  Propagates all other exceptions.

    :param updates_queue: A queue to put real-time updates into
    :param req_id: The request ID attached to this request
    :param future: The future itself
    """
    try:
        download_result = future.result()
        updates_queue.sync_q.put_nowait(
            {
                "req_id": req_id,
                "status": UpdateStatusCode.COMPLETED,
                "pretty_name": download_result.pretty_name,
                "key": download_result.key,
                "path": download_result.info_file.parent,
                "info_file": download_result.info_file,
                "video_file": download_result.video_file,
                "audio_file": download_result.audio_file,
            }
        )
    except AlreadyDownloaded as exc:
        updates_queue.sync_q.put_nowait(
            {"status": UpdateStatusCode.ERROR, "msg": f'"{exc.key}" already downloaded', "req_id": req_id}
        )
        logger.info('Request %s for "%s" was already downloaded', req_id, exc.key)
    except Exception as exc:  # noqa: B902
        updates_queue.sync_q.put_nowait({"status": UpdateStatusCode.ERROR, "msg": str(exc), "req_id": req_id})
        logger.info("Request %s got an exception", req_id, exc_info=True)


async def download_handler(request: web.Request) -> web.Response:
    """
    Handles a request to download a video/audio file.  Does type checking, issues the rest, and immediately returns 202.

    :param request: JSON request with keys: url, download_video, extract_audio, and optionally audio_quality
    :return: :mod:`aiohttp` mandated response type: 202 on success or 400 on bad request parameters
    """
    loop = asyncio.get_running_loop()

    try:
        req_params = await request.json()
    except JSONDecodeError:
        raise web.HTTPBadRequest(text="Request body must be JSON")

    if not isinstance(req_params.get("url"), str):
        raise web.HTTPBadRequest(text='"url" must be specified and be a string')

    if not isinstance(req_params.get("download_video"), bool):
        raise web.HTTPBadRequest(text='"download_video" must be specified and be a boolean')

    if not isinstance(req_params.get("extract_audio"), bool):
        raise web.HTTPBadRequest(text='"extract_audio" must be specified and be a boolean')

    if not isinstance(req_params.get("audio_quality", 3), int) or not 1 <= req_params.get("quality_quality", 3) <= 5:
        raise web.HTTPBadRequest(text='"audio_quality" must be between 1-5')

    req_id = str(uuid4())

    future = loop.run_in_executor(
        request.app["executor"],
        download,
        pathlib.Path(request.app["download_dir"]),
        True,
        req_params["url"],
        req_params.get("download_video"),
        req_params.get("extract_audio"),
        req_params.get("audio_quality", 3),
        request.app["updates_queue"],
        req_id,
        request.app["ffmpeg_dir"],
    )
    # typeshed has a bug, see https://github.com/python/typeshed/pull/3935
    future.add_done_callback(partial(download_future_handler, request.app["updates_queue"], req_id))  # type: ignore

    return web.json_response({"req_id": req_id}, status=202)


async def delete_handler(request: web.Request) -> web.Response:
    """
    Handles requests to delete a particular result.  The input directory is checked for path traversal attacks.

    :param request: JSON request with keys: key
    :return: :mod:`aiohttp` mandated response type: 200 on success or 400 on bad request parameters
    """
    try:
        req_params = await request.json()
    except JSONDecodeError:
        raise web.HTTPBadRequest(text="Request body must be JSON")

    if not isinstance(req_params.get("key"), str):
        raise web.HTTPBadRequest(text='"key" must be specified and be a string')

    resolved_dir = (request.app["download_dir"] / pathlib.Path(req_params.get("key"))).resolve()
    try:
        resolved_dir.relative_to(request.app["download_dir"])
    except ValueError:
        raise web.HTTPBadRequest(text="key specified is forbidden")

    if resolved_dir.is_dir():
        shutil.rmtree(resolved_dir)
    else:
        raise web.HTTPBadRequest(text="key does not exist")

    request.app["updates_queue"].sync_q.put_nowait({"status": UpdateStatusCode.DELETED, "key": req_params["key"]})

    return web.Response(status=200)


async def start_background_tasks(app: web.Application) -> None:
    """
    Startup function for aiohttp.  Kicks off the update publisher in the background.

    :param app: Reference to the overall application.
    """
    app["update_publisher"] = asyncio.create_task(update_publisher(app))


async def cleanup_background_tasks(app: web.Application) -> None:
    """
    Cleanup function for aiohttp.  Shuts down remaining tasks and disconnects open websockets.

    :param app: Reference to the overall application.
    """
    app["executor"].shutdown()
    app["update_publisher"].cancel()
    await app["update_publisher"]

    for ws in set(app["websockets"]):
        await ws.close(code=WSCloseCode.GOING_AWAY, message="Server shutdown")


async def init_queue(app: web.Application) -> None:
    """
    Janus Queues require the asyncio event loop to be running so this creations needs to be done in a start-up handler
    rather than the synchronous `server` function.

    :param app: Reference to the overall application.
    """
    app["updates_queue"] = Queue()


def server(
    download_dir: pathlib.Path, download_prefix: str, port: int, ffmpeg_dir: Optional[pathlib.Path] = None
) -> None:
    """
    Starts the API server.

    :param download_dir: Local directory to store downloaded files in.
    :param download_prefix: Prefix for returned file paths, ultimately used to create download links.
    :param port: TCP port to bind on.
    :param ffmpeg_dir: Directory containing the FFmpeg binaries.
    """
    app = web.Application()
    app.on_startup.append(init_queue)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    app["download_dir"] = download_dir
    app["download_prefix"] = pathlib.Path(download_prefix)
    app["ffmpeg_dir"] = ffmpeg_dir
    app["websockets"] = WeakSet()

    app.add_routes(
        [
            web.post("/download", download_handler),
            web.get("/status", websocket_handler),
            web.delete("/remove", delete_handler),
        ]
    )

    with ThreadPoolExecutor() as executor:
        app["executor"] = executor
        web.run_app(app, port=port)
