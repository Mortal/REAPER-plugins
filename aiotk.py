import asyncio
import subprocess
import tkinter


def window_closed(tk: tkinter.Tk) -> bool:
    try:
        return not tk.winfo_exists()
    except tkinter.TclError:
        # May happen if the root was destroyed
        return True


async def tk_mainloop(tk: tkinter.Tk) -> None:
    while not window_closed(tk):
        tk.update()
        await asyncio.sleep(0)


async def tkprompt(
    button_label: str = "Submit",
    title: str = "Prompt",
    prompt: str = "",
    initial: str = "",
) -> str | None:
    from tkinter import ttk

    root = tkinter.Tk()
    root.title(title)
    frm = ttk.Frame(root, padding=10)
    frm.grid()
    if prompt:
        ttk.Label(frm, text=prompt).grid(column=0, row=0, columnspan=2)
    namewidget = ttk.Entry(frm)
    namewidget.grid(column=0, row=1)
    if initial:
        namewidget.insert(0, initial)
    result: str | None = None

    def submit(v: str | None) -> None:
        nonlocal result
        result = v
        root.destroy()

    ttk.Button(frm, text=button_label, command=lambda: submit(namewidget.get())).grid(
        column=1, row=1
    )
    namewidget.bind("<Return>", lambda _event: submit(namewidget.get()))
    namewidget.bind("<Escape>", lambda _event: submit(None))
    namewidget.focus_set()
    await tk_mainloop(root)
    return result


async def tksubprocess(
    cmdline: list[str] | tuple[str, ...],
    *,
    title: str = "Terminak",
    stderr: int | None = subprocess.STDOUT,
) -> int | None:
    from tkinter import ttk

    root = tkinter.Tk()
    root.title(title)
    frm = ttk.Frame(root, padding=10)
    frm.grid()
    textwidget = tkinter.Text(frm, width=90, height=30)
    textwidget.grid(column=0, row=0)

    p = await asyncio.create_subprocess_exec(
        *cmdline, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr
    )

    async def process_stdout() -> None:
        assert p.stdout is not None
        while True:
            line = await p.stdout.readline()
            if not line:
                await p.wait()
                break
            textwidget.insert("end", line.decode("utf-8", errors="replace"))
            textwidget.see("end")

    process_stdout_task = asyncio.create_task(process_stdout())
    mainloop_task = asyncio.create_task(tk_mainloop(root))
    done, pending = await asyncio.wait(
        (process_stdout_task, mainloop_task), return_when=asyncio.FIRST_COMPLETED
    )
    if mainloop_task in pending:
        root.destroy()
        await mainloop_task
        return await p.wait()
    else:
        p.terminate()
        await process_stdout_task
        return None


async def main() -> None:
    s = await tkprompt()
    if s:
        import shlex

        cmdline = shlex.split(s)
        exitcode = await tksubprocess(cmdline)
        if exitcode:
            print(f"Exited with code {exitcode}")


if __name__ == "__main__":
    asyncio.run(main())
