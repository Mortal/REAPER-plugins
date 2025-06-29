import argparse
import socket
import struct


parser = argparse.ArgumentParser()
parser.add_argument("menu")

OP_GFX_SHOWMENU = 160
OP_GFX_SHOWMENU_REPLY = 161


def main() -> None:
    args = parser.parse_args()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', 32569))
    header = s.recv(4)
    if header != b"Mav\n":
        print(header)
        return
    x = 0
    y = 0
    menustr = args.menu.encode()
    msglen = 9 + len(menustr)
    payload = struct.pack('<IBII', msglen, OP_GFX_SHOWMENU, x, y) + menustr
    s.sendall(payload)
    s.shutdown(socket.SHUT_WR)
    data = b''
    while len(data) < 5:
        chunk = s.recv(4096)
        if not chunk:
            print("Early EOF")
            return
        data += chunk
    if data[0] != OP_GFX_SHOWMENU_REPLY:
        print("Unknown response opcode")
    n, = struct.unpack("<I", data[1:5])
    print(n)
    s.close()


if __name__ == "__main__":
    main()
