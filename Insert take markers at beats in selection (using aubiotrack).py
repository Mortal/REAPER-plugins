import asyncio
import collections
import os
import subprocess

import autil
import rutil
from reaper_python import *
from reaper_loop import reaper_loop_run
from rutil import RMediaItem, RMediaItemTake


async def amain() -> None:
    time_selection = rutil.get_time_selection()
    sources = [(item, item.active_take, autil.script_get_selected_audio_source(item)) for item in rutil.get_item_selection()]
    result: list[list[float]] = []
    for item, take, source_slice in sources:
        shift = source_slice.slice.start
        source_slice = await autil.cut_source_slice_into_new_file(source_slice)
        path = source_slice.path
        assert os.path.exists(path)
        proc = await asyncio.subprocess.create_subprocess_exec(
            "aubiotrack", path, stdout=subprocess.PIPE
        )
        assert proc.stdout is not None
        stdout_bytes, _ = await proc.communicate()
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"aubiotrack exited with code {exitcode}")
        toks = stdout_bytes.decode().split()
        if not toks:
            raise Exception("aubiotrack detected no beats in the selection")
        srctimes = [srcpos + shift for srcpos in map(float, toks)]
        result.append(srctimes)
    with rutil.undoblock("Insert take markers at beats in selection (using aubiotrack)"):
        for (item, take, time_range), srctimes in zip(sources, result):
            for srcpos in srctimes:
                take.add_take_marker(srcpos, name="", color=0)
    RPR_UpdateArrange()


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
