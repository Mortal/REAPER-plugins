import asyncio
import os
import tempfile
from typing import Literal

from reaper_python import *
from reaper_loop import reaper_loop_run
import rutil


async def gnome_term_prompt_for_input(message: str, initial: str = "") -> str | None:
    outfile = tempfile.mktemp(prefix="prompt", suffix=".txt")
    code = f"""if 1:
    import readline
    print({message!r}, flush=True)
    readline.set_startup_hook(lambda: readline.insert_text({initial!r}))
    readline.redisplay()
    try:
        s = input()
    except (EOFError, KeyboardInterrupt):
        pass
    else:
        with open({outfile!r}, "w") as fp:
            fp.write(s)
    """
    try:
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal", "--wait", "--", "python3", "-c", code
        )
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"gnome-terminal/python failed with exit code {exitcode}")
        try:
            with open(outfile) as fp:
                return fp.read()
        except FileNotFoundError:
            return None
    finally:
        try:
            os.remove(outfile)
        except OSError:
            pass


async def amain() -> None:
    projpath, _ = RPR_GetProjectPath("", rutil.MAX_STRBUF)
    searchterm = await gnome_term_prompt_for_input(
        "\nEnter yt-dlp search term\n", "ytsearch:"
    )
    if not searchterm or searchterm.strip() == "ytsearch:":
        return
    filename = await run_ytdlp(searchterm.strip(), projpath)
    with rutil.undoblock("Download audio"):
        rutil.clear_item_selection()
        RPR_InsertMedia(filename, 1)


async def run_ytdlp(searchterm: str, outdir: str) -> str:
    tmpfile = tempfile.mktemp(prefix="path", suffix=".txt")
    try:
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal",
            "--wait",
            "--",
            "yt-dlp",
            "-P",
            outdir,
            "-f",
            "m4a",
            "--print-to-file",
            "after_move:filepath",
            tmpfile,
            "--",
            searchterm,
        )
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"yt-dlp failed with exit code {exitcode}")
        try:
            with open(tmpfile) as fp:
                path = fp.read()
        except FileNotFoundError:
            raise Exception(f"yt-dlp did not write to {tmpfile}")
    finally:
        try:
            os.remove(tmpfile)
        except OSError:
            pass
    return path.strip()


def main() -> None:
    reaper_loop_run(amain())


if __name__ == "__main__":
    main()
