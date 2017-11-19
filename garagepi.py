import bluetooth
import pem
import errno
import sys
import bcrypt
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
def load_keyfile(keyfile: str) -> List[str]:
    keys = pem.parse_file(keyfile)
    print("Successfully loaded keyfile {}".format(keyfile))
    return keys


def verify_challenge(response: str, salt: str, key: str):
    correct_response = bcrypt.hashpw(key, salt)
    return bcrypt.checkpw(response, correct_response)


try:
    trusted_keys = load_keyfile(sys.argv[0])
except IOError as e:
    print(e)
    exit(errno.EACCES)

uuid = "9d298d8d-06b4-4da5-b913-0440aa7b4c70"
server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
server_sock.bind(("", 0))
server_sock.listen(1)
bluetooth.advertise_service(server_sock, "garagepi", uuid)

while True:
    client_sock, client_address = server_sock.accept()
    print("Accepted connection from {}".format(client_address))
    client_sock.close()
