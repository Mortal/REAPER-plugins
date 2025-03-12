import asyncio
import collections
import math
import os
import subprocess
from collections.abc import Sequence
from typing import Literal

from reaper_python import *
from reaper_loop import reaper_loop_run
import autil
import rutil


def compute_median(xs: Sequence[float]) -> float:
    return sorted(xs)[len(xs)//2]


def compute_diff(xs: Sequence[float], n: int) -> list[float]:
    return [(b - a) / n for a, b in zip(xs, xs[n:])]


def compute_mode(xs: Sequence[int]) -> int:
    return max(collections.Counter(xs).items(), key=lambda x: x[1])[0]


async def amain() -> None:
    item = rutil.script_get_single_selected_media_item()
    source_slice = autil.script_get_selected_audio_source(item)
    time_selection = rutil.get_time_selection()
    source_slice = await autil.cut_source_slice_into_new_file(source_slice)
    item_range = source_slice.item_time_range
    track = item.track
    path = source_slice.path
    startoffs = source_slice.startoffs
    playrate = source_slice.playrate
    itempos = source_slice.itemstart

    assert os.path.exists(path)
    proc = await asyncio.subprocess.create_subprocess_exec(
        "aubiotrack", path, stdout=subprocess.PIPE
    )
    assert proc.stdout is not None
    stdout_bytes, _ = await proc.communicate()
    exitcode = await proc.wait()
    if exitcode:
        raise Exception(f"aubiotrack exited with code {exitcode}")
    times = [
        (float(tok) - startoffs) / playrate + itempos
        for tok in stdout_bytes.decode().split()
    ]
    if not times:
        raise Exception("aubiotrack detected no beats in the item's source")
    if len(times) == 1:
        raise Exception("aubiotrack only detected 1 beat in the item's source")
    assert times == sorted(times)
    # for t in times[::-1]:
    #      RPR_SplitMediaItem(item.item, t)
    # RPR_UpdateArrange()
    # return
    if len(times) <= 2:
        n = 1
    elif len(times) <= 4:
        n = 2
    elif len(times) <= 8:
        n = 4
    else:
        n = 8
    diffs = compute_diff(times, n)

    def try_bpm(bpm: float) -> tuple[float, float]:
        # Compute modulo offsets and put into N bins
        phase_01 = [(x % (60 / bpm)) * bpm / 60 for x in times]
        phase_int = [int(p * len(times)) for p in phase_01]
        # Use mode as the offset
        offset_01 = compute_mode(phase_int) / len(times)
        # Now peaks are at offset + i * (60 / bpm)
        phase_offs = [(p - offset_01 + 0.5) % 1.0 for p in phase_01]
        phase_corrections = [p - 0.5 for p in phase_offs if 0.25 <= p <= 0.75]
        avg_correction = sum(phase_corrections) / len(phase_corrections)
        offset_01 -= avg_correction
        loss = sum(min((abs(p - offset_01), abs(p - 1 - offset_01), abs(p + 1 - offset_01)))**2 for p in phase_01) / len(phase_01)
        offset = offset_01 * 60 / bpm
        print(f"{bpm=} {offset_01=} {avg_correction=} {phase_corrections[0]=} {loss=}")
        return loss, offset

    bpm = 60 / compute_median(diffs)
    _loss, offset = min((try_bpm(bpm), try_bpm(round(bpm))))

    with rutil.undoblock("Run beat detection"):
        if time_selection:
            start = min(time_selection.start, itempos)
        else:
            start = itempos
        firstbeat = offset + 60 / bpm * max(0, math.floor((start - offset) / 60 * bpm))
        firstbeat_qn = RPR_TimeMap2_timeToQN(None, firstbeat)
        firstbeat_qn_floor = math.floor(firstbeat_qn - 0.5)
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
