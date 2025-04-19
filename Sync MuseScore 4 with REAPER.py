import asyncio
import json
import random
import sys
import traceback
from typing import Any, Callable

import aiohttp
from aiohttp import web

import rutil
from reaper_loop import reaper_loop_run


async def websocket_server_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await handle_sync_connection(ws)
    return ws


async def server_main() -> None:
    server = web.Server(websocket_server_handler)
    runner = web.ServerRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8085)
    await site.start()
    print("Listening on 8085")


local_action: asyncio.Future[Any] | None = None


async def detect_remote_play_pause(proj: rutil.RProject) -> None:
    global local_action
    local_action = asyncio.Future()
    remote_state = None
    while True:
        if the_connection is None:
            if remote_state is not None:
                print("Lost connection")
            await asyncio.sleep(0)
            remote_state = None
            continue
        ref = 2 + random.randrange(2**30)
        fut = asyncio.Future[Any]()
        refs[ref] = fut.set_result
        if remote_state is None:
            print("Send getPlayState")
        await the_connection.send_str(json.dumps({"t": "getPlayState", "ref": ref}))
        await asyncio.wait([fut, local_action], timeout=1, return_when=asyncio.FIRST_COMPLETED)
        print(fut.done(), local_action.done())
        refs.pop(ref, None)
        if local_action.done():
            while local_action.done():
                local_playing, local_position = local_action.result()
                local_action = asyncio.Future()
                ref = 2 + random.randrange(2**30)
                fut = asyncio.Future[Any]()
                refs[ref] = fut.set_result
                await the_connection.send_str(json.dumps({"t": "setPlayState", "currentlyPlaying": local_playing, "pos": local_position, "ref": ref}))
                await asyncio.wait([fut, local_action], timeout=1, return_when=asyncio.FIRST_COMPLETED)
                refs.pop(ref, None)
            continue
        if not fut.done():
            print("timeout...")
            continue
        reply = fut.result()
        if remote_state is None:
            print("Got play state", reply)
        if remote_state is not None and remote_state["currentlyPlaying"] != reply["currentlyPlaying"]:
            if reply["currentlyPlaying"]:
                print("Remote started playing")
                proj.set_edit_cursor(reply["pos"], moveview=False, seekplay=True)
                proj.play()
                # Get and ignore local_action
                await local_action
                local_action = asyncio.Future()
            else:
                print("Remote stopped playing")
                proj.stop()
                # Get and ignore local_action
                await local_action
                local_action = asyncio.Future()
        remote_state = reply


async def detect_local_play_pause(proj: rutil.RProject) -> None:
    global remote_state

    state1 = proj.get_play_state()
    # position1 = proj.get_play_position()
    # print(state1, position1)
    while True:
        await asyncio.sleep(0)
        state2 = proj.get_play_state()
        position2 = proj.get_play_position()
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


async def handle_sync_connection(ws) -> None:
    global the_connection

    await ws.send_str(json.dumps({"t": "hello", "protocol": "musicsync", "version": 1, "ref": 1}))
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            obj = json.loads(msg.data)
            # print("Got message", obj)
            if obj["t"] == "helloReply" and obj["protocol"] == "musicsync" and obj["version"] == 1 and obj["ref"] == 1:
                print("I'm the connection now")
                the_connection = ws
            elif "ref" in obj and obj["ref"] in refs:
                # print("Pass reply to future")
                refs.pop(obj["ref"])(obj)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print("WebSocket client error")
            break
        else:
            print("WebSocket client unknown message")
    print("Connection done")


async def amain() -> None:
    proj = rutil.get_current_project_index_name()[0]
    server_task = asyncio.create_task(server_main())
    local_task = asyncio.create_task(detect_local_play_pause(proj))
    remote_task = asyncio.create_task(detect_remote_play_pause(proj))
    async with aiohttp.ClientSession() as session:
        print("Connecting to 8084")
        try:
            async with session.ws_connect('http://localhost:8084') as ws:
                try:
                    await handle_sync_connection(ws)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except OSError:
            print("OSError involving websocket connection, ignoring")
    await server_task
    await local_task
    await remote_task


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
