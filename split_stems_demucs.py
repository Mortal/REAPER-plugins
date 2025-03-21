import asyncio
import os
from typing import Literal

import split_stems


async def split_stems_demucs(
    *,
    two_stems: Literal["bass", "drums", "vocals"] | None = None,
    modelname: Literal["mdx_extra_q", "htdemucs"] = "htdemucs",
) -> None:
    if two_stems is not None:
        two_stems_arg = ["--two-stems", two_stems]
        stems = [f"{two_stems}", f"no_{two_stems}"]
    else:
        two_stems_arg = []
        stems = ["bass", "drums", "vocals", "other"]

    prep = await split_stems.prep_split_stems(0.5)
    filename_fmt = f"{prep.basename}_{{stem}}_split_by_demucs.wav"
    filenames = [filename_fmt.format(stem=s) for s in stems]
    paths = [os.path.join(prep.dirname, f) for f in filenames]
    opaths = [os.path.join(prep.dirname, modelname, f) for f in filenames]
    if not all(os.path.exists(p) for p in paths):
        proc = await asyncio.subprocess.create_subprocess_exec(
            "gnome-terminal",
            "--geometry=122x10",
            "--wait",
            "--",
            "demucs",
            *two_stems_arg,
            "-n",
            modelname,
            "--float32",
            "-o",
            prep.dirname,
            "--filename",
            filename_fmt,
            prep.source_slice.path,
        )
        exitcode = await proc.wait()
        if exitcode:
            raise Exception(f"gnome-terminal/demucs failed with exit code {exitcode}")
        assert all(os.path.exists(p) for p in opaths)
        for finalpath, outpath in zip(paths, opaths):
            os.rename(outpath, finalpath)
    split_stems.insert_split_stems(prep, paths)
