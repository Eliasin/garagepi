import bluetooth
import errno
import sys
import bcrypt
import os
import time
import RPi.GPIO as GPIO
import picamera
import boto3
from botocore.exceptions import ClientError
from typing import List, Callable, Tuple
import select
import io
import argparse
from functools import partial

relay_ch1_pin = 37

face_similarity_threshold = 80.0


class Button:
    def __init__(self, input_pin: int, pull_direction):
        GPIO.setup(input_pin, GPIO.IN, pull_up_down=pull_direction)
        self.input_pin = input_pin

        if pull_direction == GPIO.PUD_UP:
            self.pressed_state = True
        else:
            self.pressed_state = False

        self.pressed_callback = None
        self.last_input = False
        self.button_input = False

    def set_pressed_callback(self, callback: Callable) -> None:
        self.pressed_callback = callback

    def poll(self) -> None:
        self.last_input = self.button_input
        self.button_input = GPIO.input(self.input_pin)

        if not self.button_input and self.last_input:
            print("Button on input pin '{}' pressed".format(self.input_pin))
            self.pressed_callback()


def print_error(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


def load_keyfile(keyfile: str) -> List[str]:
    with open(keyfile, "a+") as f:
        f.seek(0)
        keys = [key.strip() for key in f]
    print("Successfully loaded keyfile {} with keys {}".format(keyfile, keys))
    return keys


def face_from_path(image_path: str):
    try:
        with open(image_path, "rb") as image:
            return image.read()
    except IOError as image_io_error:
        print(image_io_error)
        return None


def image_verify_face(rekognition_client, source_faces: bytes, target_faces: bytes) -> bool:
    if rekognition_client is None:
        print("Facial verification disabled")
        return False
    try:
        print("Sending AWS Rekognition request")
        response = rekognition_client.compare_faces(
            SourceImage={'Bytes': source_faces},
            TargetImage={'Bytes': target_faces},
            SimilarityThreshold=face_similarity_threshold
        )
        return len(response["FaceMatches"]) >= 1
    except ClientError as e:
        print_error(e)
        return False


def bucket_verify_face(rekognition_client, source_faces: bytes, bucket_name: str, bucket_object: str) -> bool:
    if rekognition_client is None:
        print("Facial verification disabled")
        return False
    try:
        print("Sending AWS Rekognition request")
        response = rekognition_client.compare_faces(
                SourceImage={'Bytes': source_faces},
                TargetImage={'S3Object': {'Bucket':  bucket_name, 'Name': bucket_object}},
                SimilarityThreshold=face_similarity_threshold
                )
        return len(response["FaceMatches"]) >= 1
    except ClientError as e:
        print_error(e)
        return False


def get_camera_byte_data() -> bytes:
    with picamera.PiCamera(resolution=(512, 512)) as camera:
        with io.BytesIO() as image_stream:
            camera.capture(image_stream, "jpeg")
            image_stream.seek(0)
            return image_stream.read()


def bucket_verify_camera_input(rekognition_client, bucket_name: str, bucket_object: str) -> bool:
    return bucket_verify_face(rekognition_client, get_camera_byte_data(), bucket_name, bucket_object)


def image_verify_camera_input(rekognition_client, trusted_faces: bytes) -> bool:
    return image_verify_face(rekognition_client, get_camera_byte_data(), trusted_faces)


def verify_challenge(response: str, challenge: bytes, keys: List[str]) -> bool:
    for key in keys:
        if bcrypt.checkpw((key.encode('utf-8') + challenge), response):
            return True
    return False


def toggle_door() -> None:
    GPIO.output(relay_ch1_pin, GPIO.LOW)
    time.sleep(0.5)
    GPIO.output(relay_ch1_pin, GPIO.HIGH)
    print("Toggled garage door")


def initialize_gpio() -> None:
    GPIO.setmode(GPIO.BOARD)

    GPIO.setup(relay_ch1_pin, GPIO.OUT)
    GPIO.output(relay_ch1_pin, GPIO.HIGH)


def initialize_arg_parser():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--keyfile", help="path to keyfile", type=str)
    parser.add_argument("--face", help="enable facial verification", action="store_true") 
    
    facial_verification_strategy_group = parser.add_mutually_exclusive_group()
    facial_verification_strategy_group.add_argument("--trusted_faces",
                                                    help="path to trusted faces (implicitly adds --face)", type=str)
    facial_verification_strategy_group.add_argument("--bucket",
                                                    help="AWS S3 bucket name and object pair for trusted faces"
                                                         " (implicitly adds --face)", type=str, nargs=2)

    return parser


def initialize_arg_flag_dependents(args):
    rekognition = None
    bucket = args.bucket

    if args.bucket is not None and args.bucket[0] is not None and args.bucket[1] is not None:
        args.face = True
        facial_verification_strategy = partial(bucket_verify_camera_input,
                                               bucket_name=bucket[0], bucket_object=bucket[1])
    else:
        if args.trusted_faces is not None:
            args.face = True
            trusted_faces = face_from_path(args.trusted_faces)
        else:
            trusted_faces = face_from_path("trusted_faces.jpg")
        facial_verification_strategy = partial(image_verify_camera_input, trusted_faces=trusted_faces)
    
    if args.face:
        rekognition = boto3.client("rekognition")
      
    return rekognition, facial_verification_strategy


def initialize_trusted_keys(keyfile_path: str) -> List[str]:
    try:
        if keyfile_path is not None:
            return load_keyfile(keyfile_path)
        else:
            return load_keyfile("keyfile.txt")
    except IOError as io_error:
        print_error(io_error)
        return []


def initialize_server_socket():
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", 0))
    server_sock.listen(1)
    server_sock.setblocking(0)

    return server_sock


def challenge_client(client_sock, trusted_keys: List[str]) -> None:
    client_sock.settimeout(20)
    client_address = client_sock.getpeername()
    print("Accepted connection from {}".format(client_address))

    challenge = bcrypt.gensalt()
    client_sock.send(challenge)
    print("Sent challenge of {} to {}.".format(challenge, client_address))

    try:
        client_response = client_sock.recv(60)
        if verify_challenge(client_response, challenge, trusted_keys):
            print("Client {} completed challenge of {}.".format(client_address, challenge))
            toggle_door()
        else:
            print("Client {} failed challenge of {}.".format(client_address, challenge))
    except bluetooth.btcommon.BluetoothError as e:
        print_error(e)
        print("Client {} timed out on challenge of {}.".format(client_address, challenge))


def main() -> None:
    parser = initialize_arg_parser()
    args = parser.parse_args()
    
    initialize_gpio()
   
    trusted_keys = initialize_trusted_keys(args.keyfile)

    uuid = "9d298d8d-06b4-4da5-b913-0440aa7b4c70"

    rekognition, facial_verification_strategy = initialize_arg_flag_dependents(args)

    try:
        server_sock = initialize_server_socket()
        bluetooth.advertise_service(server_sock, "garagepi", uuid)
        read_sockets = [server_sock]

        button_input_pin = 16
        button = Button(button_input_pin, GPIO.PUD_UP)

        def challenge_camera():
            if facial_verification_strategy(rekognition_client=rekognition):
                print("Face accepted")
                toggle_door()
            else:
                print("Face rejected/AWS error")
        button.set_pressed_callback(challenge_camera)

        while True:
            button.poll()
            select_timeout = 0.2
            readable, writable, errored = select.select(read_sockets, [], [], select_timeout)
            for socket in readable:
                try:
                    client_sock = socket.accept()[0]
                    challenge_client(client_sock, trusted_keys)
                finally:
                    client_sock.close()
    
    finally:
        if type(server_sock) is bluetooth.bluez.BluetoothSocket:
            server_sock.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as keyboard_interrupt:
        GPIO.cleanup()
        exit()
