import bluetooth
import pem
from Crypto.PublicKey import RSA
import errno
import sys
from typing import List


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


if len(sys.argv) != 2:
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
