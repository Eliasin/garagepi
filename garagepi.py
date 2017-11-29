import bluetooth
import errno
import sys
import bcrypt
import os
import time
import RPi.GPIO as GPIO
from typing import List

GPIO.setmode(GPIO.BOARD)

relay_ch1_pin = 37
GPIO.setup(relay_ch1_pin, GPIO.OUT)

def print_error(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


if len(sys.argv) > 2:
    print(
        "Usage:\n"
        "garagepi <keyfile>"
        )
    exit(0)


def load_keyfile(keyfile: str) -> List[str]:
    with open(keyfile, "a+") as f:
        f.seek(0)
        keys = [key.strip() for key in f]
    print("Successfully loaded keyfile {} with keys {}".format(keyfile, keys))
    return keys


def verify_challenge(response: str, challenge: bytes, keys: List[str]) -> bool:
    for key in keys:
        if bcrypt.checkpw((key.encode('utf-8') + challenge), response):
            return True
    return False


def open_door():
    GPIO.output(relay_ch1_pin, GPIO.LOW)
    time.sleep(0.5)
    GPIO.output(relay_ch1_pin, GPIO.HIGH)
    print("Toggled garage door")


def get_random_bytes(n: int) -> bytes:
    return os.urandom(n)


def main():
    try:
        if len(sys.argv) == 1:
            trusted_keys = load_keyfile("keyfile.txt")
        else:
            trusted_keys = load_keyfile(sys.argv[0])
    except IOError as e:
        print_error(e)
        trusted_keys = []
        exit(errno.EACCES)

    uuid = "9d298d8d-06b4-4da5-b913-0440aa7b4c70"
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", 0))
    server_sock.listen(1)
    bluetooth.advertise_service(server_sock, "garagepi", uuid)

    while True:
        client_sock, client_address = server_sock.accept()
        client_sock.settimeout(20)
        print("Accepted connection from {}".format(client_address))

        challenge = bcrypt.gensalt()
        client_sock.send(challenge)
        print("Sent challenge of {} to {}.".format(challenge, client_address))

        try:
            client_response = client_sock.recv(60)
            if verify_challenge(client_response, challenge, trusted_keys):
                print("Client {} completed challenge of {}.".format(client_address, challenge))
                open_door()
            else:
                print("Client {} failed challenge of {}.".format(client_address, challenge))
        except bluetooth.btcommon.BluetoothError as e:
            print_error(e)
            print("Client {} timed out on challenge of {}.".format(client_address, challenge))

        client_sock.close()

try:
    main()
except KeyboardInterrupt as e:
    GPIO.cleanup()
