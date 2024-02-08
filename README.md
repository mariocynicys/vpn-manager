A server to add and remove OpenVPN clients, fully accessible by external users.
Exposes a port which users can hit to request/delete openVPN clients.

Created for personal use and intended to make creating clients accessible by others and free of charge.

#### WARNING: You shouldn't have other than one instance of this server running on a machine. If two or more instances are used in the same machine, one instance **WILL WRONGFULLY DELETE** the clients created by another.
#### WARNING: Your OpenVPN server should have no clients before running this service, otherwise, deletion requests **WILL DELETE** wrong clients.

## About the driver program:
It's an executable program that MUST support two commands.

- A `new` command to add a new client and give it the name `ID`. This command should return the content of the newly created ovpn file.
  ```bash
  $ ./program new ID
  ```
- A `revoke` command to remove the client with index `INDEX` from the designated OpenVPN server.
  ```bash
  $ ./program revoke INDEX
  ```
The program MUST not hang for any reason. And should return `0` on success and a non-zero number on failure.

## Try it:
This server is deployed on a cloud VM in Frankfurt, Germany.
To interact with the server, hit one of these endpoints:
- [/new](http://vpn.mariocynicys.me/new)
- [/delete](http://vpn.mariocynicys.me/delete)
- [/ip](http://vpn.mariocynicys.me/ip)

## How to deploy:
- First, install OpenVPN server using `openvpn-install.sh` script. After installing, don't delete the script since it's used to add and remove clients as well.
- Install nginx and copy `/etc/nginx/sites-enabled/vpn-manager.conf` to the same path in your VM. Don't forget to set `<YOUR-DOMAIN-NAME>` & `<VPN-MANAGER-PORT>` placeholders. The domain name is the one configured to route to the VM's IP from your DNS provider, and the port is the one which the VPN manager is running on (which is 8000 by default).
- Start nginx (`systemctl start nginx`).
- Make sure that ports 80 (used by nginx) and OpenVPN server port are accessible on your firewall rules and your cloud provider's network security group rules as well. OpenVPN server port is the one selected when installing OpenVPN and not the one used by the VPN manager.
- All done. Users should visit `<YOUR-DOMAIN-NAME>` and download a VPN client and will be able to connect to your VPN server.

# Disclaimer
## There are probably many security flaws in this code. PRs are appreciated.
