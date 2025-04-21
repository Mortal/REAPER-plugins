import asyncio
import json
import random
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Callable

import aiohttp
from aiohttp import web

import rutil
from reaper_loop import reaper_loop_run
from reaper_python import RPR_parse_timestr_pos


@dataclass(kw_only=True, frozen=True)
class Context:
    first_measure_start: float


async def server_main(port: int, ctx: Context) -> None:
    async def websocket_server_handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await handle_sync_connection(ctx, ws)
        return ws

    server = web.Server(websocket_server_handler)
    runner = web.ServerRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()


local_action: asyncio.Future[Any] | None = None


async def detect_remote_play_pause(ctx: Context, proj: rutil.RProject) -> None:
    global local_action
    local_action = asyncio.Future()
    remote_state = None
    while True:
        if the_connection is None:
            if remote_state is not None:
                print("Sync: Lost connection")
            await asyncio.sleep(0)
            remote_state = None
            continue
        ref = 2 + random.randrange(2**30)
        fut = asyncio.Future[Any]()
        refs[ref] = fut.set_result
        if remote_state is None:
            print("Sync: Send first getPlayState")
        await the_connection.send_str(json.dumps({"t": "getPlayState", "ref": ref}))
        await asyncio.wait([fut, local_action], timeout=1, return_when=asyncio.FIRST_COMPLETED)
        refs.pop(ref, None)
        if local_action.done():
            while local_action.done():
                local_playing, local_position = local_action.result()
                local_action = asyncio.Future()
                ref = 2 + random.randrange(2**30)
                fut = asyncio.Future[Any]()
                refs[ref] = fut.set_result
                if local_playing:
                    print("Sync: Local started playing", local_position)
                else:
                    print("Sync: Local stopped playing")
                req = {"t": "setPlayState", "currentlyPlaying": local_playing, "pos": local_position, "ref": ref}
                await the_connection.send_str(json.dumps(req))
                await asyncio.wait([fut, local_action], timeout=1, return_when=asyncio.FIRST_COMPLETED)
                if fut.done():
                    remote_state = req
                elif not local_action.done():
                    print("Sync: timeout in setPlayState...")
                refs.pop(ref, None)
            continue
        if not fut.done():
            print("Sync: timeout in getPlayState...")
            continue
        reply = fut.result()
        if remote_state is None:
            print("Sync: Got first play state")
        if remote_state is not None and remote_state["currentlyPlaying"] != reply["currentlyPlaying"]:
            if reply["currentlyPlaying"]:
                print("Sync: Remote started playing", reply.get("pos"))
                proj.set_edit_cursor(reply["pos"] + ctx.first_measure_start, moveview=False, seekplay=True)
                proj.play()
                # Get and ignore local_action
                await local_action
                local_action = asyncio.Future()
            else:
                print("Sync: Remote stopped playing")
                proj.stop()
                # Get and ignore local_action
                await local_action
                local_action = asyncio.Future()
        remote_state = reply


async def detect_local_play_pause(ctx: Context, proj: rutil.RProject) -> None:
    global remote_state

    state1 = proj.get_play_state()
    # position1 = proj.get_play_position() - ctx.first_measure_start
    # print(state1, position1)
    while True:
        await asyncio.sleep(0)
        position2 = proj.get_play_position() - ctx.first_measure_start
        state2 = 0 if position2 < 0 else proj.get_play_state()
        if state1 == 0 and state2 == 1:
            # print("Pause -> Play", the_connection is None, remote_state)
            if local_action is not None:
                local_action.set_result((True, position2))
        if state1 == 1 and state2 == 0:
            # print("Play -> Pause")
            if local_action is not None:
                local_action.set_result((False, position2))
        state1 = state2
        # position1 = position2


the_connection: Any | None = None
refs: dict[int, Callable[[Any], None]] = {}


async def handle_sync_connection(ctx: Context, ws) -> None:
    global the_connection

    await ws.send_str(json.dumps({"t": "hello", "protocol": "musicsync", "version": 1, "ref": 1}))
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            obj = json.loads(msg.data)
            if obj["t"] == "helloReply" and obj["protocol"] == "musicsync" and obj["version"] == 1 and obj["ref"] == 1:
                print("Sync: New remote connection established")
                the_connection = ws
            elif "ref" in obj and obj["ref"] in refs:
                refs.pop(obj["ref"])(obj)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print("Sync: WebSocket client error")
            break
        else:
            print("Sync: WebSocket client unknown message")
    print("Sync: Connection done")


async def amain() -> None:
    proj = rutil.get_current_project_index_name()[0]
    ctx = Context(first_measure_start=RPR_parse_timestr_pos('1.1.00', 2))
    server_task = asyncio.create_task(server_main(8085, ctx))
    local_task = asyncio.create_task(detect_local_play_pause(ctx, proj))
    remote_task = asyncio.create_task(detect_remote_play_pause(ctx, proj))
    async with aiohttp.ClientSession() as session:
        print("Sync: Listening on 8085, connecting to 8084")
        try:
            async with session.ws_connect('http://localhost:8084') as ws:
                try:
                    await handle_sync_connection(ctx, ws)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except OSError:
            print("Sync: OSError involving websocket connection, ignoring")
    await server_task
    await local_task
    await remote_task


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
