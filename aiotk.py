import asyncio
import tkinter


async def tk_mainloop(tk: tkinter.Tk) -> None:
    while True:
        try:
            if not tk.winfo_exists():
                break
        except tkinter.TclError:
            # May happen if the root was destroyed
            break
        tk.update()
        await asyncio.sleep(0)


async def main_example() -> None:
    from tkinter import ttk

    root = tkinter.Tk()
    frm = ttk.Frame(root, padding=10)
    frm.grid()
    ttk.Label(frm, text="Hello World!").grid(column=0, row=0)
    ttk.Button(frm, text="Quit", command=root.destroy).grid(column=1, row=0)
    await tk_mainloop(root)


if __name__ == "__main__":
    asyncio.run(main_example())
