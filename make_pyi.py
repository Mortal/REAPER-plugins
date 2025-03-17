"Generate reaper_python.pyi"
import collections
import re
import urllib.request


def get_reascripthelp() -> bytes:
    try:
        with open("reascripthelp.html", "rb") as fp:
            return fp.read()
    except FileNotFoundError:
        pass
    with urllib.request.urlopen(
        "https://www.reaper.fm/sdk/reascript/reascripthelp.html"
    ) as o:
        s = o.read()
    with open("reascripthelp.html", "wb") as ofp:
        ofp.write(s)
    return s


reapertypes = collections.defaultdict(lambda: "?")
reapertypes.update({
    "MediaItem": "MediaItem",
    "MediaTrack": "MediaTrack",
    "ReaProject": "ReaProject | None",
    "Int": "int",
    "Boolean": "bool",
    "Float": "float",
    "String": "str",
    "MediaItem_Take": "MediaItem_Take",
    "AudioAccessor": "AudioAccessor",
    "PCM_source": "PCM_source",
    "KbdSectionInfo": "KbdSectionInfo",
    "TrackEnvelope": "TrackEnvelope",
    "bool": "bool",
    "IReaperControlSurface": "IReaperControlSurface",
    "int": "int",
    "HWND": "HWND",
    "RECT": "RECT",
    "GUID": "GUID",
    "PCM_source*": "PCM_sourceLP | None",
    "MediaItem_Take*": "MediaItem_TakeLP | None",
    "Unknown": "object",
    "unsigned int": "int",
    "joystick_device": "joystick_device",
    "double": "float",
    "void": "object",
})


varnames = {"in": "in_"}


def main() -> None:
    print("from typing import NewType\n\n")
    for v in reapertypes.values():
        v = v.split()[0]
        if v not in dir(__builtins__):
            print(f'{v} = NewType("{v}", object)')
    print("\n")
    for line in get_reascripthelp().decode().splitlines():
        if not line.startswith('<div class="p_func">'):
            continue
        c = line[line.index("<code>") : line.index("</code>")].removeprefix("<code>")
        c = re.sub(r"<[^>]*>", "", c)
        typstr = c[c.index("(") : c.index(")")].removeprefix("(")
        typs = (
            {
                v: k
                for kv in typstr.split(",")
                for k, v in [kv.strip().removeprefix("const ").rsplit(None, 1)]
            }
            if typstr
            else {}
        )
        if c.startswith("("):
            o, f = c.split("=")
            ot = "tuple[{}]".format(
                ', '.join(reapertypes[t.removeprefix("const ").split()[0]] for t in o.strip("( )").split(","))
            )
            params = [
                p.strip()
                for p in f[f.index("(") : f.index(")")].removeprefix("(").split(",")
            ]
        else:
            funsig, paramstr = c.split("(")
            if " " in funsig:
                o, f = funsig.split()
                ot = reapertypes[o]
            else:
                f = funsig
                ot = "None"
            paramstr = paramstr.strip(")")
            params = [p.split()[-1] for p in paramstr.split(",")] if paramstr else []
        funname = f.split("(")[0].strip()
        plist = ", ".join(f"{varnames.get(p, p)}: {reapertypes[typs[p]]}" for p in params)
        print(f"def {funname}({plist}) -> {ot}: ...")
    if "?" in reapertypes.values():
        print('\n'.join(f'"{v}": "{v}",' for v, t in reapertypes.items() if t == "?"))


if __name__ == "__main__":
    main()
