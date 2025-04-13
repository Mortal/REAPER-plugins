import asyncio
import json
import re
import subprocess

from reaper_loop import reaper_loop_run


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


async def just_run(cmdline: list[str] | tuple[str, ...]) -> None:
    assert cmdline
    print(" ".join(cmdline))
    proc = await asyncio.subprocess.create_subprocess_exec(*cmdline)
    exitcode = await proc.wait()
    if exitcode:
        raise Exception(f"{cmdline[0]} exited with code {exitcode}")


async def amain(*, in_reaper: bool) -> None:
    pw_dump = json.loads(await get_output(("pw-dump",)))

    inname = {}
    outputs = {}
    nodename = {}
    links = []
    defaults = {}
    for obj in pw_dump:
        if obj["type"] == "PipeWire:Interface:Link":
            out = obj["info"]["output-port-id"]
            inp = obj["info"]["input-port-id"]
            links.append((out, inp))
        if obj["type"] == "PipeWire:Interface:Node":
            nam = obj["info"]["props"].get("node.name")
            if nam is not None:
                nodename[nam] = obj["id"]
        if obj["type"] == "PipeWire:Interface:Port":
            portname = obj["info"]["props"].get("port.alias")
            portdir = obj["info"]["props"].get("port.direction")
            if portname is not None and portdir is not None:
                if portdir == "in":
                    inname[obj["id"]] = portname
                else:
                    assert portdir in ("in", "out")
                    outputs[obj["id"]] = (
                        obj["info"]["props"]["node.id"],
                        obj["info"]["props"]["port.id"],
                        portname,
                    )
        if obj["type"] == "PipeWire:Interface:Metadata":
            if obj["props"]["metadata.name"] == "default":
                for md in obj["metadata"]:
                    if md["subject"] == 0 and md["type"] == "Spa:String:JSON":
                        defaults[md["key"]] = md["value"]["name"]

    if "default.audio.sink" not in defaults:
        raise SystemExit("don't know the default.audio.sink")
    defaultnode = nodename[defaults["default.audio.sink"]]
    defaultportids = [oid for oid in outputs if outputs[oid][0] == defaultnode]
    defaultportids.sort(key=lambda oid: outputs[oid][1])
    if len(defaultportids) < 2:
        raise SystemExit("Need at least 2 default ports")
    monitorlinks = [
        {inp for out, inp in links if out == portid} for portid in defaultportids
    ]

    input_has_link = set(inp for out, inp in links)
    reaper_ins = {}
    free_ins = []
    for inp in inname:
        mo = re.match(r"REAPER:in(\d+)$", inname[inp])
        if mo is None:
            continue
        reaper_ins[int(mo.group(1))] = inp
        if inp not in input_has_link:
            free_ins.append(int(mo.group(1)))
    if not reaper_ins:
        raise SystemExit("did not find any REAPER input ports??")
    assert sorted(reaper_ins) == list(range(1, max(reaper_ins) + 1))

    in1s = {chan for chan, portid in reaper_ins.items() if portid in monitorlinks[0]}
    in2s = {chan for chan, portid in reaper_ins.items() if portid in monitorlinks[1]}
    if in1s or in2s:
        linked_pair = in1s & {i - 1 for i in in2s}
        if not linked_pair:
            raise SystemExit(
                "REAPER already linked to monitor of default sink, but not in a stereo pair???"
            )
        stereo_in = max(linked_pair)
    else:
        if not free_ins:
            raise SystemExit("All inputs are bound to REAPER")
        free_stereo_pairs = {i for i in free_ins if i % 2} & {i - 1 for i in free_ins}
        if not free_stereo_pairs:
            raise SystemExit("No free input stereo pair")
        # Pick highest free stereo input pair
        stereo_in = max(free_stereo_pairs)
        in1 = reaper_ins[stereo_in]
        in2 = reaper_ins[stereo_in + 1]
        out1 = defaultportids[0]
        out2 = defaultportids[1]
        await just_run(("pw-link", outputs[out1][2], inname[in1]))
        await just_run(("pw-link", outputs[out2][2], inname[in2]))

    if not in_reaper:
        return

    import rutil

    sel = rutil.get_track_selection()
    if not sel:
        print("No track selected")
        return

    assert stereo_in >= 1
    for track in sel:
        track.recmon = 0
        track.recinput = 1024 | (stereo_in - 1)


def main() -> None:
    if "RPR_runloop" in globals():
        reaper_loop_run(amain(in_reaper=True))
    else:
        asyncio.run(amain(in_reaper=False))


if __name__ == "__main__":
    main()
