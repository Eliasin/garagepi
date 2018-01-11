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
from typing import List, Callable
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

        if self.button_input == False and self.last_input == True:
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


def bucket_verify_camera_input(rekognition_client, bucket_name: str, bucket_object: str) ->  bool:
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


def initialize_GPIO() -> None:
    GPIO.setmode(GPIO.BOARD)

    GPIO.setup(relay_ch1_pin, GPIO.OUT)
    GPIO.output(relay_ch1_pin, GPIO.HIGH)


def initialize_arg_parser() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyfile", help="path to keyfile", type=str)
    parser.add_argument("--face", help="enable facial verification", action="store_true")
    parser.add_argument("--trusted_faces", help="path to trusted faces", type=str)
    parser.add_argument("--bucket_name", help="AWS S3 bucket name for trusted faces", type=str)
    parser.add_argument("--bucket_object", help="name of object in S3 bucket", type=str)

    return parser


def initialize_arg_flags(args) -> None:
    rekognition = None
    trusted_faces = None
    bucket_name = None
    bucket_object = None
    if args.face:
        rekognition = boto3.client("rekognition")
        if args.trusted_faces is not None:
            trusted_faces = face_from_path(args.trusted_faces)
        else:
            trusted_faces = face_from_path("trusted_faces.jpg")
        
        if args.bucket_name is not None and args.bucket_object is not None:
            bucket_name = args.bucket_name
            bucket_object = args.bucket_object
    
    return rekognition, trusted_faces, bucket_name, bucket_object


def initialize_trusted_keys(keyfile_path: str) -> List[str]:
    try:
        if keyfile_path is not None:
            return load_keyfile(args.keyfile)
        else:
            return load_keyfile("keyfile.txt")
    except IOError as io_error:
        print_error(io_error)
        trusted_keys = []
        exit(errno.EACCES)


def initialize_server_socket() -> None:
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


def get_facial_verification_strategy(bucket_name: str, bucket_object: str, trusted_faces: bytes) -> Callable:
    if bucket_name is not None and bucket_object is not None:
        return partial(bucket_verify_camera_input, bucket_name=bucket_name, bucket_object=bucket_object)
    else:
        return partial(image_verify_camera_input, trusted_faces=trusted_faces)


def main() -> None:
    parser = initialize_arg_parser()
    args = parser.parse_args()
    
    initialize_GPIO()
   
    trusted_keys = initialize_trusted_keys(args.keyfile)

    uuid = "9d298d8d-06b4-4da5-b913-0440aa7b4c70"

    rekognition, trusted_faces, bucket_name, bucket_object = initialize_arg_flags(args)
    
    facial_verification_strategy = get_facial_verification_strategy(bucket_name, bucket_object, trusted_faces)

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
                client_sock = server_sock.accept()[0]
                try:
                    challenge_client(client_sock, trusted_keys)
                finally:
                    client_sock.close()
    
    finally:
        server_sock.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as keyboard_interrupt:
        GPIO.cleanup()
        exit()
