#!/bin/bash

# remove comment for easier troubleshooting
#set -x

. /opt/victronenergy/serial-starter/run-service.sh

app="python /opt/victronenergy/dbus-renogy-dcc/dbus-renogy-dcc.py"
args="/dev/$tty"
start $args