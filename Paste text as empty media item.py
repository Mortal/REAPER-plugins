import asyncio
import subprocess

import rutil
from reaper_loop import reaper_loop_run
from reaper_python import RPR_Main_OnCommand, RPR_GetSetMediaItemInfo_String


async def get_output(cmdline: list[str] | tuple[str, ...]) -> str:
    assert cmdline
    proc = await asyncio.subprocess.create_subprocess_exec(
        *cmdline, stdout=subprocess.PIPE
    )
    assert proc.stdout is not None
    stdout_bytes, _ = await proc.communicate()
    exitcode = await proc.wait()
    if exitcode:
        raise Exception(f"{cmdline[0]} exited with code {exitcode}")
    return stdout_bytes.decode()


async def amain(*, in_reaper: bool) -> None:
    sel = rutil.get_track_selection()
    if not sel:
        print("No track selected")
        return

    text = await get_output(("wl-paste", "-n"))
    with rutil.undoblock("Paste text as empty media item"):
        INSERT_EMPTY_ITEM = 40142
        sel1 = rutil.get_item_selection()
        RPR_Main_OnCommand(INSERT_EMPTY_ITEM, 0)
        item, = rutil.get_item_selection()
        rutil.set_item_selection(sel1)
        timesel = rutil.get_time_selection()
        if timesel is not None:
            item.time_range = timesel
        else:
            proj = rutil.get_current_project_index_name()[0]
            play_state = proj.get_play_state()
            if play_state:
                item.position = proj.get_play_position() - 0.5

        RPR_GetSetMediaItemInfo_String(item.item, "P_NOTES", text, True)
        rutil.set_item_selection([item])


def main() -> None:
    reaper_loop_run(amain(in_reaper=True))


if __name__ == "__main__":
    main()

