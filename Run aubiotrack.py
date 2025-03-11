import asyncio
import collections
import math
import os
import subprocess
from collections.abc import Sequence
from typing import Literal

from reaper_python import *
from reaper_loop import reaper_loop_run
import rutil


def compute_median(xs: Sequence[float]) -> float:
    return sorted(xs)[len(xs)//2]


def compute_diff(xs: Sequence[float]) -> list[float]:
    return [b - a for a, b in zip(xs, xs[1:])]


def compute_mode(xs: Sequence[int]) -> int:
    return max(collections.Counter(xs).items(), key=lambda x: x[1])[0]


async def amain() -> None:
    item = rutil.script_get_single_selected_media_item()
    track = item.track
    take = item.active_take
    src = take.source
    path = src.path
    # mastertrack = RPR_GetMasterTrack(None)
    itempos = item.position
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
    diffs = compute_diff(times)
    modulus = compute_median(diffs)
    # Compute modulo offsets and put into N bins
    phase_int = [int(((x % modulus) / modulus) * len(times)) for x in times]
    # Use mode as the offset
    offset = compute_mode(phase_int) / len(times) * modulus
    # Now peaks are at offset + i * modulus

    bpm = 60 / modulus
    with rutil.undoblock("Run beat detection"):
        firstbeat = itempos + offset
        firstbeat_qn = RPR_TimeMap2_timeToQN(None, firstbeat)
        firstbeat_qn_floor = math.floor(firstbeat_qn)
        firstbeat_qn_floor_time = RPR_TimeMap2_QNToTime(None, firstbeat_qn_floor)
        if (firstbeat_qn - firstbeat_qn_floor) > 0.001:
            tempbpm = 60 / (firstbeat - firstbeat_qn_floor_time)
            RPR_SetTempoTimeSigMarker(None, -1, firstbeat_qn_floor_time, -1, -1, tempbpm, 0, 0, False)
        RPR_SetTempoTimeSigMarker(None, -1, firstbeat, -1, -1, bpm, 0, 0, False)
        RPR_UpdateArrange()


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
