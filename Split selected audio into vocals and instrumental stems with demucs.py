import asyncio
import os
from typing import Literal

from reaper_python import *
from reaper_loop import reaper_loop_run
import autil
import rutil


async def amain() -> None:
    modelname: Literal["mdx_extra_q", "htdemucs"] = "htdemucs"
    two_stems: Literal["bass", "drums", "vocals"] | None = None  # "vocals"

    item = rutil.script_get_single_selected_media_item()
    track = item.track
    source_slice = autil.script_get_selected_audio_source(item)
    if source_slice.slice_fraction < 0.5:
        source_slice = await autil.cut_source_slice_into_new_file(source_slice)

    if two_stems is not None:
        two_stems_arg = ["--two-stems", two_stems]
        outputs = [f"{two_stems}", f"no_{two_stems}"]
    else:
        two_stems_arg = []
        outputs = ["bass", "drums", "vocals", "other"]

    dirname = os.path.dirname(source_slice.path)
    basename = os.path.basename(source_slice.path)
    filename_fmt = f'{basename}_{{stem}}_split_by_demucs.wav'
    filenames = [filename_fmt.format(stem=s) for s in outputs]
    paths = [os.path.join(dirname, modelname, f) for f in filenames]
    if not all(os.path.exists(p) for p in paths):
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal", "--geometry=122x10", "--wait", "--",
            "demucs", *two_stems_arg, "-n", modelname, "--float32", "-o", dirname, "--filename", filename_fmt, source_slice.path
        )
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"gnome-terminal/demucs failed with exit code {exitcode}")

    with rutil.undoblock("Split stems"):
        item.selected = False
        rutil.clear_selection()
        items = []
        for stem_path in paths:
            RPR_InsertMedia(stem_path, 1)
            item2 = rutil.script_get_single_selected_media_item()
            take2 = item2.active_take
            item2.time_range = source_slice.item_time_range
            take2.playrate = source_slice.playrate
            take2.startoffs = source_slice.startoffs
            item2.selected = False
            items.append(item2)
        rutil.set_selection(items)
        track.muted = True


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
