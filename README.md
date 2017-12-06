# garagepi

Bluetooth server application intended for opening garage doors with bluetooth enabled phones or devices. Implemented in python 3.

## Parts
* [Raspberry Pi 3 Model B](https://www.raspberrypi.org/products/raspberry-pi-3-model-b/)
* [Waveshare RPi Relay Board](https://www.waveshare.com/rpi-relay-board.htm)
* Some wires

## Dependencies
Garagepi requires:
* bcm2835
* wiringPi
* bcrypt*
* PyBluez*
* RPi.GPIO*
* typing*

Though some of these may be installed be default.

\*Installed via pip/pip3

## Installation

### Installing Dependencies
First, clone the repo:
```
git clone https://github.com/Eliasin/garagepi.git
```

To install wiringPi:
```
sudo apt install wiringpi
```

To install bcm2835:
1. Download the latest version of the library from [here](http://www.airspayce.com/mikem/bcm2835/)
2. Follow the instructions given on the page

To install pip libraries:
```
cd garagepi
pip3 install -r requirements.txt
```

### Workarounds
Since sdptool in [broken](https://raspberrypi.stackexchange.com/questions/41776/failed-to-connect-to-sdp-server-on-ffffff000000-no-such-file-or-directory) in BlueZ 5, to run the garagepi server, you must use a workaround.

#### Running the bluetoothd daemon in compatibility mode:
Edit the file
```
/etc/systemd/system/dbus-org.bluez.service
```
and change

`ExecStart=/usr/lib/bluetooth/bluetoothd`

to:

`ExecStart=/usr/lib/bluetooth/bluetoothd --compat`

### Changing sdp permissions:
Run:

`sudo chmod 777 /var/run/sdp`

Note: This will have to be run every time the pi restarts, so you may want to put it in [rc.local](https://www.raspberrypi.org/documentation/linux/usage/rc-local.md)
