# garagepi

Bluetooth server application intended for opening garage doors with bluetooth enabled phones or devices. Implemented in python 3.

## Parts
* [Raspberry Pi 3 Model B](https://www.raspberrypi.org/products/raspberry-pi-3-model-b/)
* [Waveshare RPi Relay Board](https://www.waveshare.com/rpi-relay-board.htm)
* Some wires

### Facial Verification
* [Camera Module V2](https://www.raspberrypi.org/products/camera-module-v2/)
* A push button

## Dependencies
Garagepi requires:
* bcm2835
* wiringPi
* More (in requirements.txt)

## Installation

### Installing Dependencies
First, clone the repo
```
git clone https://github.com/Eliasin/garagepi.git
```

To install wiringPi
```
sudo apt install wiringpi
```

To install bcm2835
1. Download the latest version of the library from [here](http://www.airspayce.com/mikem/bcm2835/)
2. Follow the instructions given on the page

To install pip libraries (You may want to use a [virtualenv](https://virtualenv.pypa.io/en/stable/)):
```
cd garagepi
pip3 install -r requirements.txt
```

### Configuring boto3
As an interface to AWS, boto3 requires the user to provide credentials. Instructions can be found [here](http://boto3.readthedocs.io/en/latest/guide/configuration.html).

### Workarounds
Since sdptool is [broken](https://raspberrypi.stackexchange.com/questions/41776/failed-to-connect-to-sdp-server-on-ffffff000000-no-such-file-or-directory) in BlueZ 5, to run the garagepi server, you must use a workaround.

#### Running the bluetoothd daemon in compatibility mode:
Edit the file
```
/etc/systemd/system/dbus-org.bluez.service
```
and change

`ExecStart=/usr/lib/bluetooth/bluetoothd`

to

`ExecStart=/usr/lib/bluetooth/bluetoothd --compat`

### Changing sdp permissions:
Run

`sudo chmod 777 /var/run/sdp`

Note: This will have to be run every time the pi restarts, so you may want to put it in [rc.local](https://www.raspberrypi.org/documentation/linux/usage/rc-local.md).

## Usage
```
usage: garagepi.py [-h] [--keyfile KEYFILE] [--face]
                   [--trusted_faces TRUSTED_FACES] [--bucket_name BUCKET_NAME]
                   [--bucket_object BUCKET_OBJECT]

optional arguments:
  -h, --help            show this help message and exit
  --keyfile KEYFILE     path to keyfile
  --face                enable facial verification
  --trusted_faces TRUSTED_FACES
                        path to trusted faces
  --bucket_name BUCKET_NAME
                        AWS S3 bucket name for trusted faces
  --bucket_object BUCKET_OBJECT
                        name of object in S3 bucket
```

## Wiring
Garagepi is intended to be used for opening garage doors that are controlled by simply completing a circuit, though it could be used for anything that requires the quick toggling of a relay remotely.

On any garage door opened like this there should be two connection points on the back for wires to be connected. Simply wire one of these points to each point on the relay channel 1, one to the middle and one to the normally closed point.
![Relay Wiring Example](https://github.com/Eliasin/garagepi/blob/master/relay.jpg)

### Facial Verification
The button used to trigger the camera module should be wired to pin 16 (board notation) and a ground pin. If pin 16 is unavailable for use, feel free to change the definition of `button_input_pin` in the main source file. 

## Planned Features
* Refactor and cleanup
