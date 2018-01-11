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
from typing import List
import select
import io
import argparse

relay_ch1_pin = 37
button_input_pin = 16

select_timeout = 0.2

face_similarity_threshold = 80.0

def print_error(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


def load_keyfile(keyfile: str) -> List[str]:
    with open(keyfile, "a+") as f:
        f.seek(0)
        keys = [key.strip() for key in f]
    print("Successfully loaded keyfile {} with keys {}".format(keyfile, keys))
    return keys


def path_to_face(image_path: str):
    try:
        with open(image_path, "rb") as image:
            return image.read()
    except IOError as image_io_error:
        return None


def verify_face(rekognition_client, source_faces, target_faces) -> bool:
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

def verify_face_against_bucket(rekognition_client, source_faces, bucket_name, bucket_object) -> bool:
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


def get_camera_byte_data():
    with picamera.PiCamera(resolution=(512, 512)) as camera:
        with io.BytesIO() as image_stream:
            camera.capture(image_stream, "jpeg")
            image_stream.seek(0)
            return image_stream.read()


def verify_camera_face_against_bucket(rekognition_client, bucket_name, bucket_object) ->  bool:
    return verify_face_against_bucket(rekognition_client, get_camera_byte_data(), bucket_name, bucket_object)


def verify_camera_face(rekognition_client, trusted_faces) -> bool:
    return verify_face(rekognition_client, get_camera_byte_data(), trusted_faces)


def verify_challenge(response: str, challenge: bytes, keys: List[str]) -> bool:
    for key in keys:
        if bcrypt.checkpw((key.encode('utf-8') + challenge), response):
            return True
    return False


def toggle_door():
    GPIO.output(relay_ch1_pin, GPIO.LOW)
    time.sleep(0.5)
    GPIO.output(relay_ch1_pin, GPIO.HIGH)
    print("Toggled garage door")


def get_random_bytes(n: int) -> bytes:
    return os.urandom(n)


def initializeGPIO() -> None:
    GPIO.setmode(GPIO.BOARD)

    GPIO.setup(relay_ch1_pin, GPIO.OUT)
    GPIO.setup(button_input_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.output(relay_ch1_pin, GPIO.HIGH)


def initializeArgParser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyfile", help="path to keyfile", type=str)
    parser.add_argument("--face", help="enable facial verification", action="store_true")
    parser.add_argument("--trusted_faces", help="path to trusted faces", type=str)
    parser.add_argument("--bucket_name", help="AWS S3 bucket name for trusted faces", type=str)
    parser.add_argument("--bucket_object", help="name of object in S3 bucket", type=str)

    return parser


def initializeArgFlags(args):
    rekognition = None
    trusted_faces = None
    bucket_name = None
    bucket_object = None
    if args.face:
        rekognition = boto3.client("rekognition")
        if args.trusted_faces is not None:
            trusted_faces = path_to_face(args.trusted_faces)
        else:
            trusted_faces = path_to_face("trusted_faces.jpg")
        
        if args.bucket_name is not None and args.bucket_object is not None:
            bucket_name = args.bucket_name
            bucket_object = args.bucket_object
    
    return rekognition, trusted_faces, bucket_name, bucket_object


def initializeTrustedKeys(keyfile_path) -> List[str]:
    try:
        if keyfile_path is not None:
            return load_keyfile(args.keyfile)
        else:
            return load_keyfile("keyfile.txt")
    except IOError as io_error:
        print_error(io_error)
        trusted_keys = []
        exit(errno.EACCES)


def main() -> None:
    parser = initializeArgParser()
    args = parser.parse_args()
    
    initializeGPIO()
   
    trusted_keys = initializeTrustedKeys(args.keyfile)

    uuid = "9d298d8d-06b4-4da5-b913-0440aa7b4c70"

    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)

    rekognition, trusted_faces, bucket_name, bucket_object = initializeArgFlags(args)
    
    try:
        server_sock.bind(("", 0))
        server_sock.listen(1)
        server_sock.setblocking(0)
        bluetooth.advertise_service(server_sock, "garagepi", uuid)
        read_sockets = [server_sock]

        last_button_input = False
        button_input = False
        while True:
            
            last_button_input = button_input
            button_input = GPIO.input(16)
            if button_input == False and last_button_input == True:
                print("Button input detected")
                if bucket_name is not None:
                    if verify_camera_face_against_bucket(rekognition, bucket_name, bucket_object):
                        print("Face accepted")
                        toggle_door()
                    else:
                        print("Face rejected/AWS error")
                else:
                    if verify_camera_face(rekognition, trusted_faces):
                        print("Face accepted")
                        toggle_door()
                    else:
                        print("Face rejected/AWS error")

            readable, writable, errored = select.select(read_sockets, [], [], select_timeout)
            for socket in readable:
                client_sock, client_address = server_sock.accept()
                try:
                    client_address = client_sock.getpeername()
                    client_sock.settimeout(20)
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
