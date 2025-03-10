import asyncio
import os
from typing import Literal

from reaper_python import *
from reaper_loop import reaper_loop_run
import rutil


async def amain() -> None:
    modelname: Literal["mdx_extra_q", "htdemucs"] = "htdemucs"
    two_stems: Literal["bass", "drums", "vocals"] | None = None  # "vocals"

    item = rutil.script_get_single_selected_media_item()
    track = RPR_GetMediaItem_Track(item)
    take = RPR_GetActiveTake(item)
    src = RPR_GetMediaItemTake_Source(take)
    src, path, _ = RPR_GetMediaSourceFileName(src, "", rutil.MAX_STRBUF)

    assert os.path.exists(path)
    dirname, filename = os.path.split(path)
    basename = os.path.splitext(path)[0]

    sourcelength, src, quarternotes = RPR_GetMediaSourceLength(src, False)
    assert not quarternotes
    itempos = RPR_GetMediaItemInfo_Value(item, "D_POSITION")
    length = RPR_GetMediaItemInfo_Value(item, "D_LENGTH")
    startoffs = RPR_GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
    playrate = RPR_GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
    timestart, timeend = itempos, itempos + length
    timestart, timeend = rutil.range_intersect(rutil.get_time_selection(), (timestart, timeend))
    assert timestart < timeend
    sourcestart = startoffs + (timestart - itempos) * playrate
    sourceend = startoffs + (timeend - itempos) * playrate
    sourcefrac = (sourceend - sourcestart) / sourcelength
    if sourcefrac < 0.5:
        cutbase = f"{basename}_{sourcestart*1000:.0f}_{sourceend*1000:.0f}"
        cutfile = os.path.join(dirname, f"{cutbase}.flac")
        if not os.path.exists(cutfile):
            proc = await asyncio.subprocess.create_subprocess_exec(
                "gnome-terminal", "--wait", "--",
                'ffmpeg', '-i', path, '-ss', str(sourcestart), '-to', str(sourceend), '-y', cutfile
            )
            await proc.wait()
        path = cutfile
        basename = cutbase
        sourceend -= sourcestart
        sourcestart = 0

    if two_stems is not None:
        two_stems_arg = ["--two-stems", two_stems]
        outputs = [f"{two_stems}", f"no_{two_stems}"]
    else:
        two_stems_arg = []
        outputs = ["bass", "drums", "vocals", "other"]

    filename_fmt = f'{basename}_{{stem}}_split_by_demucs.wav'
    filenames = [filename_fmt.format(stem=s) for s in outputs]
    paths = [os.path.join(dirname, modelname, f) for f in filenames]
    if not all(os.path.exists(p) for p in paths):
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal", "--geometry=122x10", "--wait", "--",
            "demucs", *two_stems_arg, "-n", modelname, "--float32", "-o", dirname, "--filename", filename_fmt, path
        )
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"gnome-terminal/demucs failed with exit code {exitcode}")

    with rutil.undoblock("Split stems"):
        RPR_SetMediaItemSelected(item, False)
        rutil.clear_selection()
        items = []
        for stem_path in paths:
            RPR_InsertMedia(stem_path, 1)
            item2 = rutil.script_get_single_selected_media_item()
            take2 = RPR_GetActiveTake(item2)
            RPR_SetMediaItemInfo_Value(item2, "D_POSITION", timestart)
            RPR_SetMediaItemInfo_Value(item2, "D_LENGTH", timeend - timestart)
            RPR_SetMediaItemTakeInfo_Value(take2, "D_PLAYRATE", playrate)
            RPR_SetMediaItemTakeInfo_Value(take2, "D_STARTOFFS", sourcestart)
            RPR_SetMediaItemSelected(item2, False)
            items.append(item2)
        rutil.set_selection(items)
        RPR_SetMediaTrackInfo_Value(track, "B_MUTE", 1.0)


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
