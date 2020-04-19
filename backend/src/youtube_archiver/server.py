import asyncio
import pathlib
from concurrent.futures import ThreadPoolExecutor
from json.decoder import JSONDecodeError
from typing import Optional
from uuid import uuid4

from aiohttp import WSMsgType, web
from janus import Queue

from .downloader import download


async def update_publisher(app: web.Application) -> None:
    try:
        while True:
            update = await app["updates_queue"].async_q.get()
            # The websocket updates are best effort, not required.  Don't wait for it to finish
            [asyncio.create_task(ws.send_update(update)) for ws in app["websockets"]]
    except asyncio.CancelledError:
        pass


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    request.app["websockets"].append(ws)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == "close":
                await ws.close()
                request.app["websockets"].remove(ws)
        elif msg.type in [WSMsgType.CLOSED, WSMsgType.ERROR]:
            request.app["websockets"].remove(ws)

    return ws


async def download_handler(request: web.Request) -> web.Response:
    loop = asyncio.get_running_loop()

    try:
        req_params = await request.json()
    except JSONDecodeError:
        raise web.HTTPBadRequest(text="Request body must be JSON")

    req_id = str(uuid4())

    loop.run_in_executor(
        request.app["executor"],
        download,
        pathlib.Path(request.app["download_dir"]),
        True,
        req_params["url"],
        True,
        True,
        5,
        request.app["updates_queue"],
        req_id,
        request.app["ffmpeg_dir"],
    )

    return web.json_response({"req_id": req_id}, status=202)


async def start_background_tasks(app: web.Application) -> None:
    app["update_publisher"] = asyncio.create_task(update_publisher(app))


async def cleanup_background_tasks(app: web.Application) -> None:
    app["executor"].shutdown()
    app["update_publisher"].cancel()
    await app["update_publisher"]


def server(download_dir: pathlib.Path, port: int, ffmpeg_dir: Optional[pathlib.Path] = None) -> None:
    app = web.Application()
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    app["download_dir"] = download_dir
    app["ffmpeg_dir"] = ffmpeg_dir
    app["websockets"] = []
    app["updates_queue"] = Queue()

    app.add_routes(
        [web.post("/download", download_handler), web.get("/status", websocket_handler)]
    )

    with ThreadPoolExecutor() as executor:
        app["executor"] = executor
        web.run_app(app, port=port)
