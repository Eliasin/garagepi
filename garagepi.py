import bluetooth
import pem
from Crypto.PublicKey import RSA
import errno
import sys


def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


if len(sys.argv) <= 1 or len(sys.argv) >= 2:
    print(
        "Usage:\n"
        "garagepi <keyfile>"
        )
    exit(0)


def load_keyfile(keyfile):
    try:
        with open(keyfile, "r+") as f:
            keys = pem.parse_file(keyfile)
        keys = list(map((lambda x: RSA.importKey(x)), keys))
        return keys
    except IOError as e:
        print_error(e)
        return None


trusted_keys = load_keyfile(sys.argv[0])

if trusted_keys is None:
    exit(errno.EACCES)
