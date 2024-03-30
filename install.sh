#!/bin/bash

# remove comment for easier troubleshooting
#set -x

# check if at least 8 MB free space is available on the system partition
freeSpace=$(df -m / | awk 'NR==2 {print $4}')
if [ $freeSpace -lt 8 ]; then

    # try to expand system partition
    bash /opt/victronenergy/swupdate-scripts/resize2fs.sh

    freeSpace=$(df -m / | awk 'NR==2 {print $4}')
    if [ $freeSpace -lt 8 ]; then
        echo
        echo
        echo "ERROR: Not enough free space on the system partition. At least 8 MB are required."
        echo
        echo "       Please please try to execute this command"
        echo
        echo "       bash /opt/victronenergy/swupdate-scripts/resize2fs.sh"
        echo
        echo "       and try the installation again after."
        echo
        echo
        exit 1
    else
        echo
        echo
        echo "INFO: System partition was expanded. Now there are $freeSpace MB free space available."
        echo
        echo
    fi

fi

# handle read only mounts
bash /opt/victronenergy/swupdate-scripts/remount-rw.sh

# install
rm -rf /opt/victronenergy/service/dbus-renogy-dcc
rm -rf /opt/victronenergy/service-templates/dbus-renogy-dcc
rm -rf /opt/victronenergy/dbus-renogy-dcc
mkdir /opt/victronenergy/dbus-renogy-dcc
mkdir /opt/victronenergy/dbus-renogy-dcc/ext
cp -f /data/etc/dbus-renogy-dcc/* /opt/victronenergy/dbus-renogy-dcc &>/dev/null
cp -rf /data/etc/dbus-renogy-dcc/ext/* /opt/victronenergy/dbus-renogy-dcc/ext &>/dev/null
cp -rf /data/etc/dbus-renogy-dcc/service /opt/victronenergy/service-templates/dbus-renogy-dcc

# check if serial-starter.d was deleted
serialstarter_path="/data/conf/serial-starter.d"
serialstarter_file="$serialstarter_path/dbus-renogy-dcc.conf"

# check if folder exists
if [ ! -d "$serialstarter_path" ]; then
    mkdir "$serialstarter_path"
fi

# check if file exists
if [ ! -f "$serialstarter_file" ]; then
    {
        echo "service renogydcc        dbus-renogy-dcc"
        echo "alias default gps:vedirect:renogydcc"
        echo "alias rs485 cgwacs:fzsonick:imt:modbus:renogydcc"
    } > "$serialstarter_file"
fi

# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local
if [ ! -f "$filename" ]; then
    echo "#!/bin/bash" > "$filename"
    chmod 755 "$filename"
fi
grep -qxF "bash /data/etc/dbus-renogy-dcc/install.sh" $filename || echo "bash /data/etc/dbus-renogy-dcc/install.sh" >> $filename

# kill driver, if running. It gets restarted by the service daemon
pkill -f "supervise dbus-renogy-dcc.*"
pkill -f "multilog .* /var/log/dbus-renogy-dcc.*"
pkill -f "python .*/dbus-renogy-dcc.py /dev/tty.*"

# install notes
echo
echo "Renogy DCC: The installation is complete!"
echo