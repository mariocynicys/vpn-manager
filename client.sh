#!/bin/bash

NULL=/dev/null
# Note: We are using timeouts so that the process doesn't hang there asking for correct input if an invalid input was passed.
if [[ $1 == "new" ]]
then
	printf "1\n $2\n" | sudo timeout 1s ./openvpn-install.sh >$NULL 2>$NULL
	# Only if the past command succeeded we can run the following block.
	if [[ $? == 0 ]]
	then
		cat /root/$2.ovpn
		# We don't want to store this file on disk
		# sudo + user input ??! crazy are you?
		sudo rm /root/$2.ovpn
	else
		exit 100
	fi
elif [[ $1 == "revoke" ]]
then
	output=$(printf "2\n $2\n y\n" | sudo timeout 1s ./openvpn-install.sh 2>$NULL)
	if [[ $? == 0 ]]
	then
		# Echo the name of the revoked client to stdout
		echo $output | awk '{print $(NF-1)}'
	else
		exit 100
	fi
else
	exit 50
fi
