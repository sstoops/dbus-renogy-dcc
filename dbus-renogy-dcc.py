#!/usr/bin/env python

# If editing then use
# svc -d /service/dbus-renogy-dcc and
# svc -u /service/dbus-renogy-dcc
# to stop and restart the service

import logging
import os
import platform
import sys
from pprint import pformat
from typing import Tuple

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

import renogy

# Victron packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "./ext/velib_python"))

from vedbus import VeDbusService
from ve_utils import exit_on_error

# Init logging
logger = logging.getLogger("dbus-renogy-dcc")
logger.setLevel(logging.INFO)

GLIB_INTERVAL = 5000
DEVICE_RETRIES = 5


class NoDeviceFoundError(Exception):
    pass


class Driver:

    device_connected = False
    device_response_error_count = 0

    def __init__(self, connection: str, device_instance: int = 0):
        self.connection = connection
        self.device_instance = device_instance
        self._bus = (
            dbus.SessionBus()
            if "DBUS_SESSION_BUS_ADDRESS" in os.environ
            else dbus.SystemBus()
        )
        self.slave_address, data = self.discover_slave_address()
        self.init_dbus(data)

    def discover_slave_address(self) -> Tuple[int, dict]:
        slave_address = 0
        print("Discovering slave address")
        while slave_address < 255:
            print(f"Trying slave address: {slave_address}")
            try:
                data = renogy.Device(
                    port=self.connection,
                    slaveaddress=slave_address,
                ).all()
                print(f"Slave address found: {slave_address}")
                return slave_address, data
            except:
                slave_address += 1
        raise NoDeviceFoundError("No device found on any slave address")

    def init_dbus(self, data: dict):
        self.dbus = VeDbusService(
            f"com.victronenergy.solarcharger.{self.connection.split('/')[-1]}",
            self._bus,
        )
        # Create the management paths
        self.dbus.add_path("/Mgmt/ProcessName", __file__)
        self.dbus.add_path(
            "/Mgmt/ProcessVersion",
            "Unkown version, and running on Python " + platform.python_version(),
        )
        self.dbus.add_path("/Mgmt/Connection", self.connection)
        self.dbus.add_path("/DeviceInstance", self.device_instance)
        self.dbus.add_path("/ProductId", 0)
        self.dbus.add_path("/ProductName", data["product_model"])
        self.dbus.add_path("/Serial", data["product_serial_number"])
        self.dbus.add_path("/FirmwareVersion", data["product_software_version"])
        self.dbus.add_path("/HardwareVersion", data["product_hardware_version"])
        self.dbus.add_path("/Connected", 1)

        power_solar = data["voltage_solar"] * data["current_solar"]
        power_alternator = data["voltage_alternator"] * data["current_alternator"]
        power_total = power_solar + power_alternator

        # Create the paths for the solar charger
        self.dbus.add_path("/Pv/0/V", data["voltage_solar"])
        self.dbus.add_path("/Pv/0/P", power_solar)
        self.dbus.add_path("/Pv/0/MppOperationMode", 2)

        # Create the paths for the DC/DC charger
        self.dbus.add_path("/Pv/1/V", data["voltage_alternator"])
        self.dbus.add_path("/Pv/1/P", power_alternator)
        self.dbus.add_path("/Pv/1/MppOperationMode", 2)

        # Create the paths for the battery
        self.dbus.add_path("/Dc/0/Voltage", data["battery_voltage"])
        self.dbus.add_path(
            "/Dc/0/Current", round(power_total / data["battery_voltage"], 2)
        )

        # Create the device paths
        self.dbus.add_path("/Yield/Power", power_total)
        self.dbus.add_path("/MppOperationMode", 2)
        # /MppOperationMode     0 = Off
        #                       1 = Voltage or Current limited
        #                       2 = MPPT Tracker active
        if data["charge_state"]["mppt_charging"]:
            self.dbus.add_path("/State", 3)
        elif data["charge_state"]["boost"]:
            self.dbus.add_path("/State", 4)
        elif data["charge_state"]["float"]:
            self.dbus.add_path("/State", 5)
        elif data["charge_state"]["equalization"]:
            self.dbus.add_path("/State", 7)
        # /State           0=Off
        #                  2=Fault
        #                  3=Bulk
        #                  4=Absorption
        #                  5=Float
        #                  6=Storage
        #                  7=Equalize
        #                  252=External control
        self.dbus.add_path("/Yield/User", round(data["power_daily"] / 1000, 3))
        self.dbus.add_path("/Yield/System", round(data["power_total"] / 1000, 2))

    def update(self) -> bool:
        try:
            data = renogy.Device(
                port=self.connection,
                slaveaddress=self.slave_address,
            ).all()
            self.device_response_error_count = 0
            # If the device was previously not connected, then set it to connected
            if not self.device_connected:
                self.device_connected = True
                self.dbus["/Connected"] = 1
        except:
            logger.exception("Device unresponsive. Retrying")
            self.device_response_error_count += 1
            # If we hit our error limit, then set the device to disconnected
            if (
                self.device_connected
                and self.device_response_error_count > DEVICE_RETRIES
            ):
                self.device_connected = False
                self.dbus["/Connected"] = 0
                raise
            return True

        logger.info(f"Device data: {pformat(data)}")

        self.dbus["/ProductName"] = data["product_model"]
        self.dbus["/HardwareVersion"] = data["product_hardware_version"]
        self.dbus["/FirmwareVersion"] = data["product_software_version"]
        self.dbus["/Serial"] = data["product_serial_number"]

        power_solar = data["voltage_solar"] * data["current_solar"]
        power_alternator = data["voltage_alternator"] * data["current_alternator"]
        power_total = power_solar + power_alternator

        if data["charge_state"]["no_charging"]:
            # 0 = Off
            self.dbus["/MppOperationMode"] = 0
        elif data["charge_state"]["current_limited"]:
            # 1 = Voltage or Current limited
            self.dbus["/MppOperationMode"] = 1
        else:
            # 2 = MPPT Tracker active
            self.dbus["/MppOperationMode"] = 2

        self.dbus["/Pv/0/V"] = data["voltage_solar"]
        self.dbus["/Pv/0/P"] = power_solar
        self.dbus["/Pv/0/MppOperationMode"] = 2
        self.dbus["/Pv/1/V"] = data["voltage_alternator"]
        self.dbus["/Pv/1/P"] = power_alternator
        self.dbus["/Yield/Power"] = round(power_total, 1)
        # solar_service["/MppOperationMode"] =

        self.dbus["/Dc/0/Voltage"] = data["battery_voltage"]
        self.dbus["/Dc/0/Current"] = round(power_total / data["battery_voltage"], 2)

        if data["charge_state"]["mppt_charging"]:
            self.dbus["/State"] = 3
        elif data["charge_state"]["boost"]:
            self.dbus["/State"] = 4
        elif data["charge_state"]["float"]:
            self.dbus["/State"] = 5
        elif data["charge_state"]["equalization"]:
            self.dbus["/State"] = 7

        self.dbus["/Yield/User"] = round(data["power_daily"] / 1000, 3)
        self.dbus["/Yield/System"] = round(data["power_total"] / 1000, 2)

        return True


def main() -> None:
    logger.info(__file__ + " is starting up")

    # Get the first argument as the connection
    if len(sys.argv) < 2:
        logger.error("No connection provided. Exiting.")
        sys.exit(1)

    connection = sys.argv[1]

    # Setup the dbus main loop
    DBusGMainLoop(set_as_default=True)

    # Create the device
    device = Driver(connection=connection)

    # Do a first update so that all the readings appear.
    device.update()

    # Setup periodic updates
    GLib.timeout_add(GLIB_INTERVAL, exit_on_error, device.update)

    # Run the main loop
    mainloop = GLib.MainLoop()
    logger.info("Connected to dbus, and switching over to GLib.MainLoop().")
    mainloop.run()


if __name__ == "__main__":
    main()
