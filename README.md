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

First, clone the repo:
`git clone https://github.com/Eliasin/garagepi.git`

To install wiringPi:
`sudo apt install wiringpi`

To install bcm2835:
1. Download the latest version of the library from [here](http://www.airspayce.com/mikem/bcm2835/)
2. Follow the instructions given on the page

To install pip libraries:
`cd garagepi`
`pip3 install -r requirements.txt`
