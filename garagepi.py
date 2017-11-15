import bluetooth
import pem
from Crypto.PublicKey import RSA
import errno
import sys
from typing import List


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


if len(sys.argv) != 1:
    print(
        "Usage:\n"
        "garagepi <keyfile>"
        )
    exit(0)


# noinspection PyProtectedMember
def load_keyfile(keyfile: str) -> List[RSA._RSAobj]:
    keys = pem.parse_file(keyfile)
    keys = list(map((lambda x: RSA.importKey(x)), keys))
    print("Successfully loaded keyfile {}".format(keyfile))
    return keys


try:
    trusted_keys = load_keyfile(sys.argv[0])
except IOError as e:
    print(e)
    exit(errno.EACCES)

server_sock = bluetooth.BluetoothSocket(bluetooth.L2CAP)
port = 0x1003
server_sock.bind(("", port))
server_sock.listen(1)

while True:
    client_sock, client_address = server_sock.accept()
    print("Accepted connection from {}".format(client_address))
    client_sock.close()

