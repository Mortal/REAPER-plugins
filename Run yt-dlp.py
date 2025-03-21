import os
import tempfile

import aiotk
from reaper_python import RPR_GetProjectPath, RPR_InsertMedia
from reaper_loop import reaper_loop_run
import rutil


async def amain() -> None:
    projpath, _ = RPR_GetProjectPath("", rutil.MAX_STRBUF)
    searchterm = await aiotk.tkprompt(
        prompt="Enter yt-dlp search term", initial="ytsearch:"
    )
    if not searchterm or searchterm.strip() == "ytsearch:":
        return
    filename = await run_ytdlp(searchterm.strip(), projpath)
    if filename is None:
        return
    with rutil.undoblock("Download audio"):
        rutil.clear_item_selection()
        RPR_InsertMedia(filename, 1)


async def run_ytdlp(searchterm: str, outdir: str) -> str | None:
    tmpfile = tempfile.mktemp(prefix="path", suffix=".txt")
    try:
        exitcode = await aiotk.tksubprocess(
            (
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
        )
        if exitcode:
            raise Exception(f"yt-dlp failed with exit code {exitcode}")
        if exitcode is None:
            return None
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
