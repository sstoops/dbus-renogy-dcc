# dbus-renogy-dcc

This is a driver for Venus OS devices (any GX device sold by Victron or a Raspberry Pi running the Venus OS image).

The driver will communicate with a Renogy DCC30S or DCC50S. The data is then published to the Venus OS system (dbus).

This driver is very new and barely tested.

It was unclear to me how to best represent the Solar and the Alternator sides of the Renogy device. For now, they're feeding into the system as two MPPT trackers, which is obviously inaccurate.
