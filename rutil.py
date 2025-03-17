import contextlib
from dataclasses import dataclass
from typing import Any, Iterator

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


@dataclass
class TimeRange:
    start: float
    end: float

    @property
    def valid_closed(self) -> bool:
        return self.start <= self.end

    @property
    def valid_open(self) -> bool:
        return self.start < self.end

    def contains(self, other: "TimeRange | float") -> bool:
        assert self.valid_closed
        if isinstance(other, TimeRange):
            assert other.valid_closed
            return self.start <= other.start and other.end <= self.end
        return self.start <= other <= self.end

    def __contains__(self, lhs: float) -> bool:
        # `lhs in self`
        assert isinstance(lhs, float)
        return self.contains(lhs)

    def __add__(self, rhs: float) -> "TimeRange":
        return TimeRange(self.start + rhs, self.end + rhs)

    def __sub__(self, rhs: float) -> "TimeRange":
        return TimeRange(self.start - rhs, self.end - rhs)

    def __mul__(self, rhs: float) -> "TimeRange":
        return TimeRange(self.start * rhs, self.end * rhs)

    def __div__(self, rhs: float) -> "TimeRange":
        return TimeRange(self.start / rhs, self.end / rhs)

    @property
    def length(self) -> float:
        assert self.valid_closed
        return self.end - self.start


def get_cursor_position_seconds() -> float:
    return RPR_GetCursorPosition()


def get_time_selection() -> TimeRange | None:
    isSet, isLoop, startOut, endOut, allowautoseek = RPR_GetSet_LoopTimeRange(
        False, False, 0.0, 0.0, False
    )
    if startOut == endOut:
        return None
    return TimeRange(startOut, endOut)


def set_time_selection(t: TimeRange) -> None:
    isSet, isLoop, startOut, endOut, allowautoseek = RPR_GetSet_LoopTimeRange(
        False, False, 0.0, 0.0, False
    )
    RPR_GetSet_LoopTimeRange(
        True, isLoop, t.start, t.end, allowautoseek
    )


MAX_STRBUF = 4 * 1024 * 1024


def range_intersect(a: TimeRange | None, b: TimeRange) -> TimeRange:
    if a is None:
        return b
    p, q = a.start, a.end
    r, s = b.start, b.end
    x = max(p, r)
    y = min(q, s)
    return TimeRange(x, y)


@dataclass
class RTrack:
    track: Any

    @property
    def muted(self) -> bool:
        return bool(RPR_GetMediaTrackInfo_Value(self.track, "B_MUTE"))

    @muted.setter
    def muted(self, v: bool) -> None:
        RPR_SetMediaTrackInfo_Value(self.track, "B_MUTE", 1.0 if v else 0.0)

    @property
    def selected(self) -> bool:
        return bool(RPR_IsTrackSelected(self.track))

    @selected.setter
    def selected(self, v: bool) -> None:
        RPR_SetTrackSelected(self.track, v)

    @property
    def name(self) -> str:
        retval, _track, name, _ = RPR_GetTrackName(self.track, "", MAX_STRBUF)
        assert retval
        return name

    # No @name.setter - there's no RPR_SetTrackName?????


@dataclass
class RMediaSource:
    src: Any

    @property
    def path(self) -> str:
        _src, path, _ = RPR_GetMediaSourceFileName(self.src, "", MAX_STRBUF)
        return path

    @property
    def length_seconds_or_quarters(self) -> tuple[float, bool]:
        sourcelength, src, quarternotes = RPR_GetMediaSourceLength(self.src, False)
        return sourcelength, quarternotes

    @property
    def length_seconds(self) -> float:
        sourcelength, quarternotes = self.length_seconds_or_quarters
        assert not quarternotes
        return sourcelength

    @property
    def maybe_length_seconds(self) -> float | None:
        sourcelength, quarternotes = self.length_seconds_or_quarters
        return None if quarternotes else sourcelength


@dataclass
class RMediaItemTake:
    take: Any

    @property
    def source(self) -> RMediaSource:
        return RMediaSource(RPR_GetMediaItemTake_Source(self.take))

    @property
    def startoffs(self) -> float:
        return RPR_GetMediaItemTakeInfo_Value(self.take, "D_STARTOFFS")

    @startoffs.setter
    def startoffs(self, v: float) -> None:
        RPR_SetMediaItemTakeInfo_Value(self.take, "D_STARTOFFS", v)

    @property
    def playrate(self) -> float:
        return RPR_GetMediaItemTakeInfo_Value(self.take, "D_PLAYRATE")

    @playrate.setter
    def playrate(self, v: float) -> None:
        RPR_SetMediaItemTakeInfo_Value(self.take, "D_PLAYRATE", v)

    def get_take_markers(self) -> list[float]:
        res: list[float] = []
        n = RPR_GetNumTakeMarkers(self.take)
        for i in range(n):
            srcpos, _take, _i, _name, _name_sz, _color_out = RPR_GetTakeMarker(self.take, i, "", MAX_STRBUF, 0)
            res.append(srcpos)
        return res

    def add_take_marker(self, srcpos: float, name: str, color: int) -> None:
        RPR_SetTakeMarker(self.take, -1, name, srcpos, color)

    def clear_take_markers(self) -> None:
        n = RPR_GetNumTakeMarkers(self.take)
        for i in range(n)[::-1]:
            RPR_DeleteTakeMarker(self.take, i)


@dataclass
class RMediaItem:
    item: Any

    @property
    def active_take(self) -> RMediaItemTake:
        return RMediaItemTake(RPR_GetActiveTake(self.item))

    @property
    def track(self) -> RTrack:
        return RTrack(RPR_GetMediaItem_Track(self.item))

    @property
    def position(self) -> float:
        return RPR_GetMediaItemInfo_Value(self.item, "D_POSITION")

    @position.setter
    def position(self, p: float) -> None:
        RPR_SetMediaItemInfo_Value(self.item, "D_POSITION", p)

    @property
    def length(self) -> float:
        return RPR_GetMediaItemInfo_Value(self.item, "D_LENGTH")

    @length.setter
    def length(self, p: float) -> None:
        RPR_SetMediaItemInfo_Value(self.item, "D_LENGTH", p)

    @property
    def timebase(self) -> float:
        return RPR_GetMediaItemInfo_Value(self.item, "C_BEATATTACHMODE")

    @timebase.setter
    def timebase(self, p: float) -> None:
        RPR_SetMediaItemInfo_Value(self.item, "C_BEATATTACHMODE", p)

    @property
    def time_range(self) -> TimeRange:
        p = self.position
        return TimeRange(p, p + self.length)

    @time_range.setter
    def time_range(self, span: TimeRange) -> None:
        self.position = span.start
        self.length = span.end - span.start

    @property
    def selected(self) -> bool:
        return RPR_IsMediaItemSelected(self.item)

    @selected.setter
    def selected(self, v: bool) -> None:
        RPR_SetMediaItemSelected(self.item, v)


def script_get_single_selected_media_item() -> RMediaItem:
    count = RPR_CountSelectedMediaItems(None)
    if not count:
        raise SystemExit("Please select a media item")
    if count > 1:
        raise SystemExit("Please select a single media item")
    return RMediaItem(RPR_GetSelectedMediaItem(None, 0))


def get_item_selection():
    return [RMediaItem(RPR_GetSelectedMediaItem(None, i)) for i in range(RPR_CountSelectedMediaItems(None))]


def clear_item_selection():
    items = get_item_selection()
    for item in items:
        item.selected = False
    return items


def set_item_selection(items):
    clear_item_selection()
    select_all(items)


def select_all(items):
    for item in items:
        item.selected = True


def get_track_selection():
    return [RTrack(RPR_GetSelectedTrack(None, i)) for i in range(RPR_CountSelectedTracks(None))]


def clear_track_selection():
    items = get_track_selection()
    for item in items:
        item.selected = False
    return items


def set_track_selection(items):
    clear_track_selection()
    select_all_tracks(items)


def select_all_tracks(items):
    for item in items:
        item.selected = True
