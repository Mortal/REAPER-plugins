import asyncio
import os
import subprocess
from typing import Literal

from reaper_python import *
from reaper_loop import reaper_loop_run
import rutil


async def amain() -> None:
    item = rutil.script_get_single_selected_media_item()
    track = RPR_GetMediaItem_Track(item)
    take = RPR_GetActiveTake(item)
    src = RPR_GetMediaItemTake_Source(take)
    src, path, _ = RPR_GetMediaSourceFileName(src, "", rutil.MAX_STRBUF)
    # mastertrack = RPR_GetMasterTrack(None)
    itempos = RPR_GetMediaItemInfo_Value(item, "D_POSITION")
    # length = RPR_GetMediaItemInfo_Value(item, "D_LENGTH")

    assert os.path.exists(path)
    proc = await asyncio.subprocess.create_subprocess_exec(
        "aubiotrack", path, stdout=subprocess.PIPE
    )
    assert proc.stdout is not None
    stdout_bytes, _ = await proc.communicate()
    exitcode = await proc.wait()
    if exitcode:
        raise Exception(f"aubiotrack exited with code {exitcode}")
    times = list(map(float, stdout_bytes.decode().split()))
    times = times[2:-2]
    if not times:
        return
    bpm = 60 * (len(times) - 1) / (times[-1] - times[0])
    with rutil.undoblock("Run beat detection"):
        RPR_SetTempoTimeSigMarker(None, -1, itempos + times[0], -1, -1, bpm, 0, 0, False)
        # for t in times:
        #     RPR_SetTakeStretchMarker(take, -1, t, t)
        RPR_UpdateArrange()


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
