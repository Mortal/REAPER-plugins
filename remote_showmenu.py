import argparse
import socket
import struct


parser = argparse.ArgumentParser()

OP_GFX_SHOWMENU = 160
OP_GFX_SHOWMENU_REPLY = 161
OP_GFX_INIT = 162
OP_GFX_QUIT = 163


class Conn:
    sock: socket.socket
    buf = b""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock

    def ensure_bytes(self, n: int) -> None:
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise Exception("Early EOF")
            self.buf += chunk

    def consume_bytes(self, n: int) -> bytes:
        res, self.buf = self.buf[:n], self.buf[n:]
        return res

    def showmenu(self, menustr: str, x: int = 0, y: int = 0) -> int:
        menubytes = menustr.encode()
        msglen = 9 + len(menubytes)
        payload = struct.pack('<IBII', msglen, OP_GFX_SHOWMENU, x, y) + menubytes
        self.sock.sendall(payload)
        self.ensure_bytes(5)
        if self.buf[0] != OP_GFX_SHOWMENU_REPLY:
            raise Exception("Unknown response opcode")
        n, = struct.unpack("<I", self.consume_bytes(5)[1:5])
        return n

    def gfx_init(self, name: str, width: int, height: int, dockstate: int, xpos: int, ypos: int) -> None:
        namebytes = name.encode()
        msglen = 21 + len(namebytes)
        self.sock.sendall(struct.pack("<IBfffff", msglen, OP_GFX_INIT, width, height, dockstate, xpos, ypos) + namebytes)

    def gfx_quit(self) -> None:
        self.sock.sendall(struct.pack("<IB", 1, OP_GFX_QUIT))


def open_conn() -> Conn:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 32569))
    header = sock.recv(4)
    if header != b"Mav\n":
        print(header)
        raise SystemExit(1)
    return Conn(sock)


def menuitem(s: str, disabled=False, checked=False) -> str:
    ch = "#" if disabled else "!" if checked else ""
    return f"{ch}{s}"


def submenu(*items: str) -> str:
    return "|".join((f">{items[0]}", *items[1:-1], f"<{items[-1]}"))


def main() -> None:
    parser.parse_args()
    conn = open_conn()
    gfx_open = False
    gfx_disabled = False
    while True:
        menuitems = [
            menuitem("close gfx" if gfx_open else "open gfx", disabled=gfx_disabled),
            submenu(
                menuitem("advanced"),
                menuitem("disable gfx", checked=gfx_disabled, disabled=gfx_open),
            ),
            menuitem("quit"),
        ]
        i = conn.showmenu("|".join(menuitems))
        print(i, len(conn.buf))
        if i == 1:
            if gfx_open:
                conn.gfx_quit()
                gfx_open = False
            else:
                conn.gfx_init("foo", 200, 150, 0, 0, 0)
                gfx_open = True
        elif i == 2:
            gfx_disabled = not gfx_disabled
        elif i == 3:
            break
    conn.sock.shutdown(socket.SHUT_WR)
    conn.sock.close()


if __name__ == "__main__":
    main()
