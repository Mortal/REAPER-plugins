import asyncio
import os
import shlex
import sys
import traceback

import rutil
import split_stems
from reaper_loop import reaper_loop_run
from reaper_python import *


async def main() -> None:
    prep = await split_stems.prep_split_stems(1.0)
    filename_fmt = f"{prep.basename}_{{stem}}_split_by_lalalai.flac"
    filenames = [filename_fmt.format(stem=s) for s in "vocals no_vocals".split()]
    paths = [os.path.join(prep.dirname, f) for f in filenames]
    if not all(os.path.exists(p) for p in paths):
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal",
            "--wait",
            "--",
            os.path.join(sys.path[0], "lalalcli"),
            str(prep.source_slice.path),
            str(prep.source_slice.slice.start),
            str(prep.source_slice.slice.end),
            paths[0],
            paths[1],
        )
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"lalalcli exited with code {exitcode}")
    split_stems.insert_split_stems(prep, paths)


reaper_loop_run(main())
