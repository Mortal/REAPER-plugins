import collections
import math
from collections.abc import Sequence

from reaper_python import *
import rutil


def compute_median(xs: Sequence[float]) -> float:
    return sorted(xs)[len(xs)//2]


def compute_diff(xs: Sequence[float], n: int) -> list[float]:
    return [(b - a) / n for a, b in zip(xs, xs[n:])]


def compute_mode(xs: Sequence[int]) -> int:
    return max(collections.Counter(xs).items(), key=lambda x: x[1])[0]


def main() -> None:
    time_selection = rutil.get_time_selection()
    times: list[float] = []
    start = float("inf") if time_selection is None else time_selection.start
    for item in rutil.get_item_selection():
        take = item.active_take
        startoffs = take.startoffs
        playrate = take.playrate
        itempos = item.position
        start = min(itempos, start)
        times += [
            (srcpos - startoffs) / playrate + itempos
            for srcpos in take.get_take_markers()
        ]
    if time_selection is not None:
        times = [t for t in times if t in time_selection]
    if not times:
        raise Exception("Please select a media item with an active take with markers")
    if len(times) == 1:
        raise Exception("Please select a media item with an active take with at least 2 markers")
    times = sorted(set(times))
    if len(times) <= 2:
        n = 1
    elif len(times) <= 4:
        n = 2
    elif len(times) <= 8:
        n = 4
    else:
        n = 8
    diffs = compute_diff(times, n)

    def try_bpm(bpm: float) -> tuple[float, float, float]:
        # Compute modulo offsets and put into N bins
        phase_01 = [(x % (60 / bpm)) * bpm / 60 for x in times]
        n_buckets = len(times)
        phase_int = [int(p * n_buckets) for p in phase_01]
        # Use mode to pick a bucket
        bucket = compute_mode(phase_int)
        # Use average phase in bucket
        in_bucket = [p for p, b in zip(phase_01, phase_int) if b == bucket]
        offset_01 = sum(in_bucket) / len(in_bucket)
        # Now peaks are at offset + i * (60 / bpm)
        phase_offs = [(p - offset_01 + 0.5) % 1.0 for p in phase_01]
        phase_corrections = [p - 0.5 for p in phase_offs if 0.25 <= p <= 0.75]
        avg_correction = sum(phase_corrections) / len(phase_corrections)
        offset_01 -= avg_correction
        # Compute loss as mean square error
        loss = sum(min((abs(p - offset_01), abs(p - 1 - offset_01), abs(p + 1 - offset_01)))**2 for p in phase_01) / len(phase_01)
        offset = offset_01 * 60 / bpm
        return loss, offset, bpm

    bpm = 60 / compute_median(diffs)
    _loss, offset, bpm = min((try_bpm(bpm), try_bpm(round(bpm))))

    with rutil.undoblock("Set tempo from take markers"):
        firstbeat = offset + 60 / bpm * max(0, math.floor((start - offset) / 60 * bpm))
        firstbeat_qn = RPR_TimeMap2_timeToQN(None, firstbeat)
        firstbeat_qn_floor = math.floor(firstbeat_qn - 0.5)
        firstbeat_qn_floor_time = RPR_TimeMap2_QNToTime(None, firstbeat_qn_floor)
        if (firstbeat_qn - firstbeat_qn_floor) > 0.001:
            tempbpm = 60 / (firstbeat - firstbeat_qn_floor_time)
            RPR_SetTempoTimeSigMarker(None, -1, firstbeat_qn_floor_time, -1, -1, tempbpm, 0, 0, False)
        RPR_SetTempoTimeSigMarker(None, -1, firstbeat, -1, -1, bpm, 0, 0, False)
        if time_selection is not None:
            rutil.set_time_selection(time_selection)
    RPR_UpdateArrange()


if __name__ == "__main__":
    main()
