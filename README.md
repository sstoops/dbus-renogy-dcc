# dbus-renogy-dcc

> [!IMPORTANT]
> This driver is very new and very untested. It does work, but much refinement is needed. Use at your own discretion!

This is a driver to enable Venus OS devices (any GX device sold by Victron or a Raspberry Pi running the Venus OS image) to communicate with a Renogy DCC30S or DCC50S.

It was unclear to me how to best represent the Solar and the Alternator sides of the Renogy device. For now, they're feeding into the system as two MPPT trackers, which is obviously inaccurate.

## Installation

Still a work in progress, but for now, on this repo to `/data/dbus-renogy-dcc` on your device, then run `/data/dbus-renogy-dcc/install.sh`.
