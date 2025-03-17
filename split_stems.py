import os
from dataclasses import dataclass

import autil
import rutil
from autil import SourceSlice
from rutil import RMediaItem
from reaper_python import RPR_InsertMedia


@dataclass
class SplitStems:
    item: RMediaItem
    source_slice: SourceSlice

    @property
    def dirname(self) -> str:
        return os.path.dirname(self.source_slice.path)

    @property
    def basename(self) -> str:
        return os.path.splitext(os.path.basename(self.source_slice.path))[0]


async def prep_split_stems(cut_fraction: float) -> SplitStems:
    assert 0 <= cut_fraction <= 1.0
    item = rutil.script_get_single_selected_media_item()
    source_slice = autil.script_get_selected_audio_source(item)
    if source_slice.slice_fraction < cut_fraction:
        source_slice = await autil.cut_source_slice_into_new_file(source_slice)
    return SplitStems(item, source_slice)


def insert_split_stems(prep: SplitStems, paths: list[str]) -> None:
    with rutil.undoblock("Split stems"):
        timebase = prep.item.timebase
        prep.item.selected = False
        rutil.clear_item_selection()
        # Select item.track to make sure new tracks are right below it
        tracks = rutil.clear_track_selection()
        prep.item.track.selected = True
        items = []
        for stem_path in paths:
            RPR_InsertMedia(stem_path, 1)
            item2 = rutil.script_get_single_selected_media_item()
            take2 = item2.active_take
            print(prep.source_slice.item_time_range)
            item2.time_range = prep.source_slice.item_time_range
            take2.playrate = prep.source_slice.playrate
            take2.startoffs = prep.source_slice.startoffs
            item2.timebase = timebase
            item2.selected = False
            items.append(item2)
        rutil.set_item_selection(items)
        prep.item.track.muted = True
        rutil.set_track_selection(tracks)
