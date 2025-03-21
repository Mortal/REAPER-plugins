import asyncio
import os
from dataclasses import dataclass

import rutil
from rutil import TimeRange, RMediaItem


@dataclass
class SourceSlice:
    path: str
    source_length: float
    slice: TimeRange
    playrate: float
    itemstart: float

    @property
    def slice_fraction(self) -> float:
        return self.slice.length / self.source_length

    @property
    def item_time_range(self) -> TimeRange:
        return TimeRange(
            self.itemstart, self.itemstart + self.slice.length / self.playrate
        )

    @property
    def startoffs(self) -> float:
        return self.slice.start


async def cut_source_slice_into_new_file(s: SourceSlice) -> SourceSlice:
    assert os.path.exists(s.path)
    dirname, filename = os.path.split(s.path)
    basename = os.path.splitext(filename)[0]
    cutbase = f"{basename}_{s.slice.start*1000:.0f}_{s.slice.end*1000:.0f}"
    cutfile = os.path.join(dirname, f"{cutbase}.flac")
    if not os.path.exists(cutfile):
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal",
            "--wait",
            "--",
            "ffmpeg",
            "-i",
            s.path,
            "-ss",
            str(s.slice.start),
            "-to",
            str(s.slice.end),
            "-y",
            cutfile,
        )
        await proc.wait()
    return SourceSlice(
        cutfile, s.slice.length, s.slice - s.slice.start, s.playrate, s.itemstart
    )


def script_get_selected_audio_source(
    item: RMediaItem, inside_time_selection: bool = True
) -> SourceSlice:
    take = item.active_take
    src = take.source
    playrate = take.playrate
    time_range = item.time_range
    assert time_range.valid_open
    if inside_time_selection:
        time_range = rutil.range_intersect(rutil.get_time_selection(), time_range)
        if not time_range.valid_open:
            raise Exception("Time selection does not overlap with given media item")
    source_range = (time_range - item.position) * playrate + take.startoffs
    return SourceSlice(
        src.path, src.length_seconds, source_range, playrate, time_range.start
    )
