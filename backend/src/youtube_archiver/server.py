import asyncio
import pathlib
from concurrent.futures import ThreadPoolExecutor

from aiohttp import WSMsgType, web
from janus import Queue


async def update_publisher(app: web.Application) -> None:
    try:
        while True:
            update = await app["updates_queue"].get()
            await asyncio.gather(*[ws.send_update(update) for ws in app["websockets"]])
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


async def start_background_tasks(app: web.Application) -> None:
    app["update_publisher"] = asyncio.create_task(update_publisher(app))


async def cleanup_background_tasks(app: web.Application) -> None:
    app["update_publisher"].cancel()
    await app["update_publisher"]


def server(download_dir: pathlib.Path, port: int) -> None:
    app = web.Application()

    app["download_dir"] = download_dir
    app["websockets"] = []
    app["updates_queue"] = Queue()

    app.add_routes([web.get("/status", websocket_handler)])

    with ThreadPoolExecutor() as executor:
        app["executor"] = executor
        web.run_app(app, port=port)
