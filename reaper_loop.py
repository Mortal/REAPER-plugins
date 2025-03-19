"""
Run asyncio code in REAPER plugins with this custom event loop.

ReaperCoopEventLoop is an asyncio event loop that cooperates with REAPER
by using RPR_runloop to schedule each iteration of the asyncio loop.

Usage:

    from reaper_python import RPR_ShowConsoleMsg
    from reaper_loop import reaper_loop_run

    async def main() -> None:
        url = 'https://github.com/adefossez/demucs/raw/refs/heads/main/test.mp3'
        proc = await asyncio.subprocess.create_subprocess_exec("wget", url)
        await proc.wait()
        RPR_InsertMedia("test.mp3", 1)

    reaper_loop_run(main)
"""
import asyncio.base_events
import logging
import sys
import traceback
import typing
from typing import Any, Awaitable, Callable, TextIO


def reaper_loop_run(f: Awaitable[None], name: str | None = None) -> None:
    if name is None:
        name = traceback.extract_stack()[1][0]
    # Need to set asyncio logger to use stdout to get unhandled exception errors
    logger = typing.cast(Any, asyncio.base_events).logger
    logger.setLevel(logging.ERROR)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    loop = ReaperCoopEventLoop()
    asyncio.set_event_loop(loop)
    loop.reaper_run_until_complete(f, name)


def reaper_run_until_complete_cb(fut):
    if not fut.cancelled():
        exc = fut.exception()
        if exc is not None:
            from reaper_python import RPR_ShowConsoleMsg

            RPR_ShowConsoleMsg("".join(traceback.format_exception(exc)))
    typing.cast(Any, asyncio.futures)._get_loop(fut).stop()


class ReaperCoopEventLoop(asyncio.SelectorEventLoop):
    reaper_script_name = "unknown"

    def reaper_run_until_complete(self, future, name: str) -> None:
        self.reaper_script_name = name
        unixloop = typing.cast(Any, self)
        unixloop._check_closed()
        unixloop._check_running()

        new_task = not asyncio.isfuture(future)
        future = asyncio.ensure_future(future, loop=self)
        future.add_done_callback(reaper_run_until_complete_cb)
        self.reaper_run_forever()
        # This yields control to REAPER, so now we have to return.

    def reaper_run_forever(self) -> None:
        from reaper_python import RPR_ShowConsoleMsg

        # The following special functions are injected by REAPER
        RPR_runloop: Callable[[str], None] = sys.modules["__main__"].RPR_runloop
        RPR_atexit: Callable[[str], None] = sys.modules["__main__"].RPR_atexit
        unixloop = typing.cast(Any, self)
        # Access methods to make sure they exist on self
        run_forever_setup = unixloop._run_forever_setup
        run_forever_cleanup = unixloop._run_forever_cleanup
        run_once = unixloop._run_once

        if unixloop._stopping:
            print("ReaperCoopEventLoop stopping early", flush=True)
            return

        try:
            run_forever_setup()
        except BaseException:
            print("ReaperCoopEventLoop crashing early", flush=True)
            run_forever_cleanup()
            raise

        runloop = f"__runloop{id(self)}"
        atexit = f"__atexit{id(self)}"

        def _atexit_coop() -> None:
            if not self.is_running():
                return
            self.stop()
            # After raising CancelledError in a coroutine,
            # it can await something new, which we can again cancel.
            # How many times should we repeat that?
            cancels = 10
            for _ in range(cancels):
                tasks = asyncio.tasks.all_tasks(self)
                if not tasks:
                    break
                for task in tasks:
                    task.cancel()
                try:
                    run_once()
                except BaseException as exc:
                    print(f"{self.reaper_script_name}({id(self)}) cancelled", flush=True)
                    run_forever_cleanup()
                    if isinstance(exc, SystemExit):
                        # Do not reraise SystemExit as it causes REAPER to exit.
                        if exc.args:
                            RPR_ShowConsoleMsg(f"{exc.args[0]}")
                        return
                    raise exc
            else:
                print(f"{self.reaper_script_name}({id(self)}) dropping {len(tasks)} stubborn tasks", flush=True)
            print(f"{self.reaper_script_name}({id(self)}) cancelled", flush=True)
            run_forever_cleanup()

        def _runloop_coop() -> None:
            try:
                unixloop.call_soon(lambda: None)
                run_once()
            except BaseException as exc:
                run_forever_cleanup()
                if isinstance(exc, SystemExit):
                    # Do not reraise SystemExit as it causes REAPER to exit.
                    if exc.args:
                        RPR_ShowConsoleMsg(f"{exc.args[0]}")
                    return
                raise exc
            if unixloop._stopping:
                print(f"{self.reaper_script_name}({id(self)}) stopping", flush=True)
                run_forever_cleanup()
            else:
                RPR_runloop(f"{runloop}()")

        setattr(sys.modules["__main__"], runloop, _runloop_coop)
        setattr(sys.modules["__main__"], atexit, _atexit_coop)
        print(f"{self.reaper_script_name}({id(self)}) starting", flush=True)
        _runloop_coop()
        RPR_atexit(f"{atexit}()")
