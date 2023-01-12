#!/bin/bash

# This scripts launches a monitoring container for the openvpn server.
# It connects to the openvpn server via management port and shows the connected clients and their traffic usage.
# You need to open management @ (172.17.0.1:<MANAGEMENT_PORT>) in your openvpn server config file.

CONTAINER_NAME=openvpn_monitor # choose any uniqe name for the container.
MANAGEMENT_PORT=5555 # management port of the openvpn server.
MONITOR_PORT=8001 # port serving the monitoring page.

if [ $1 == 'start' ]
then
    docker run -d --rm --name $CONTAINER_NAME \
        --add-host=host.docker.internal:host-gateway \
        -e OPENVPNMONITOR_DEFAULT_MAPS=True \
        -e OPENVPNMONITOR_SITES_0_ALIAS=TCP \
        -e OPENVPNMONITOR_SITES_0_HOST=host.docker.internal \
        -e OPENVPNMONITOR_SITES_0_NAME=TCP \
        -e OPENVPNMONITOR_SITES_0_PORT=$MANAGEMENT_PORT \
        -e OPENVPNMONITOR_SITES_0_SHOWDISCONNECT=True \
        -p $MONITOR_PORT:80 ruimarinho/openvpn-monitor
elif [ $1 == 'stop' ]
then
    docker stop $CONTAINER_NAME
elif [ $1 == 'restart' ]
then
    $0 stop
    $0 start
else
    echo "Usage: $0 start|stop|restart"
    exit 1
fi