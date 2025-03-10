import contextlib
from dataclasses import dataclass
from typing import Iterator

from reaper_python import *


@dataclass
class UndoBlock:
    name: str


@contextlib.contextmanager
def undoblock(name: str) -> Iterator[UndoBlock]:
    block = UndoBlock(name)
    RPR_Undo_BeginBlock2(None)
    try:
        yield block
    finally:
        RPR_Undo_EndBlock2(None, block.name, 0)


def clear_selection():
    items = [RPR_GetSelectedMediaItem(None, i) for i in range(RPR_CountSelectedMediaItems(None))]
    for item in items:
        RPR_SetMediaItemSelected(item, False)
    return items


def set_selection(items):
    clear_selection()
    select_all(items)


def select_all(items):
    for item in items:
        RPR_SetMediaItemSelected(item, True)


@dataclass
class TimeRange:
    start: float
    end: float


def get_time_selection() -> TimeRange | None:
    isSet, isLoop, startOut, endOut, allowautoseek = RPR_GetSet_LoopTimeRange(
        False, False, 0.0, 0.0, False
    )
    if startOut == endOut:
        return None
    return TimeRange(startOut, endOut)


def script_get_single_selected_media_item() -> "MediaItem":
    count = RPR_CountSelectedMediaItems(None)
    if not count:
        raise SystemExit("Please select a media item")
    if count > 1:
        raise SystemExit("Please select a single media item")
    return RPR_GetSelectedMediaItem(None, 0)


MAX_STRBUF = 4 * 1024 * 1024


def range_intersect(
    a: TimeRange | None, b: tuple[float, float]
) -> tuple[float, float]:
    if a is None:
        return b
    p, q = a.start, a.end
    r, s = b
    return max(p, r), min(q, s)
