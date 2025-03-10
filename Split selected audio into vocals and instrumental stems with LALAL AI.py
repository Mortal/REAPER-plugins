import os
import shlex
import sys
import traceback

import rutil
from reaper_python import *


def main() -> None:
    item = rutil.script_get_single_selected_media_item()
    track = RPR_GetMediaItem_Track(item)
    take = RPR_GetActiveTake(item)
    src = RPR_GetMediaItemTake_Source(take)
    src, path, _ = RPR_GetMediaSourceFileName(src, "", rutil.MAX_STRBUF)
    itempos = RPR_GetMediaItemInfo_Value(item, "D_POSITION")
    length = RPR_GetMediaItemInfo_Value(item, "D_LENGTH")
    startoffs = RPR_GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
    playrate = RPR_GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
    timestart, timeend = rutil.range_intersect(
        rutil.get_time_selection(), (itempos, itempos + length)
    )
    sourcestart = startoffs + (timestart - itempos) * playrate
    sourceend = startoffs + (timeend - itempos) * playrate
    dirname, filename = os.path.split(path)
    basename = os.path.splitext(path)[0]
    stem_path = os.path.join(
        dirname,
        f"{basename}-{timestart*1000:.0f}-{timeend*1000:.0f}_vocals_split_by_lalalai.flac",
    )
    back_path = os.path.join(
        dirname,
        f"{basename}-{timestart*1000:.0f}-{timeend*1000:.0f}_no_vocals_split_by_lalalai.flac",
    )
    if not RPR_file_exists(stem_path) and not RPR_file_exists(back_path):
        cmdline = (
            os.path.join(sys.path[0], "gnome-terminal-wrapper"),
            str(path),
            str(sourcestart),
            str(sourceend),
            stem_path,
            back_path,
        )
        execretval = RPR_ExecProcess(" ".join(map(shlex.quote, cmdline)), 0)
        exitcode = int(execretval[: execretval.index("\n")])
        if exitcode:
            raise SystemExit(f"lalalcli exited with code {exitcode}")
    RPR_Undo_BeginBlock2(None)
    try:
        RPR_SetMediaItemSelected(item, False)

        RPR_InsertMedia(stem_path, 1)
        item2 = rutil.script_get_single_selected_media_item()
        take2 = RPR_GetActiveTake(item2)
        RPR_SetMediaItemInfo_Value(item2, "D_POSITION", timestart)
        RPR_SetMediaItemInfo_Value(item2, "D_LENGTH", timeend - timestart)
        RPR_SetMediaItemTakeInfo_Value(take2, "D_PLAYRATE", playrate)
        RPR_SetMediaItemSelected(item2, False)

        RPR_InsertMedia(back_path, 1)
        item3 = rutil.script_get_single_selected_media_item()
        take3 = RPR_GetActiveTake(item3)
        RPR_SetMediaItemInfo_Value(item3, "D_POSITION", timestart)
        RPR_SetMediaItemInfo_Value(item3, "D_LENGTH", timeend - timestart)
        RPR_SetMediaItemTakeInfo_Value(take3, "D_PLAYRATE", playrate)

        RPR_SetMediaItemSelected(item2, True)
        RPR_SetMediaTrackInfo_Value(track, "B_MUTE", 1.0)
    finally:
        RPR_Undo_EndBlock2(None, f"Split stems", 0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        if exc.args:
            RPR_ShowConsoleMsg(f"{exc.args[0]}")
