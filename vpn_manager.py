import os
import shutil
import pickle
import logging
import subprocess
from uuid import uuid4
from collections import defaultdict, OrderedDict
from typing import List, Dict


class VPNManager:
    """A manager that handles creating/revoking vpn clients and other stuff."""

    def __init__(self):
        self.program = ''
        """The path to an executable program that can add and revoke vpn clients."""
        self.client_count = 0
        """The current number of registered clients that the vpn manager knows of."""
        self.max_client_count = 0
        """The maximum number of clients which this vpn manager can handle."""
        self.max_clients_per_user = 0
        """The maximum number of clients a single IP can own."""
        # FIXME: List non-efficient. Consider changing to a datatype that better fit our case.
        self.clients: List[str] = []
        """A list of all the registered clients."""
        self.max_cache_size = 0
        """The maximum number of ovpn files to store in memory."""
        self.cache: OrderedDict = OrderedDict()
        """A cache to hold ovpn recently requested files."""
        self.user_clients_map: Dict[str, List[str]] = defaultdict(list)
        """A map of the IPs linked to the clients they instanciated."""

    def new(self, user: str) -> str:
        """Adds a new client to the vpn server.
        Returns the ovpn file as a string and the newly created client ID."""
        # Check if we can't allocate any more clients.
        if len(self.clients) >= self.max_client_count:
            raise RuntimeError(
                "Reached the maximum number of registered clients.")
        # Check if this user already has a lot of clients.
        if len(self.user_clients_map[user]) >= self.max_clients_per_user:
            raise RuntimeError(
                "You have already allocated many clients. Please delete some.")
        # Get a client.
        client_id = str(uuid4())
        output = subprocess.run(
            [self.program, 'new', client_id], stdout=subprocess.PIPE)
        if output.returncode != 0:
            # Log the error.
            logging.error("{} exitted with status code {} while adding a new client.".format(
                self.program, output.returncode))
            raise RuntimeError(
                "Couldn't add a new client. Contact the vpn server admin.")
        # Store the client ID.
        self.clients.append(client_id)
        # Cache the ovpn file.
        self.cache[client_id] = output.stdout
        # Remember that this user owns the just created client.
        self.user_clients_map[user].append(client_id)
        # If we hit the maximum cache size, the first half have probably
        # stayed there for so long. Delete it to free some memory.
        if len(self.cache) == self.max_cache_size:
            logging.info("Hit the maximum ovpn file count. Pruning {} ovpn files.".format(self.max_cache_size / 2))
            while len(self.cache) > self.max_cache_size / 2:
                # last=False pops the first item.
                self.cache.popitem(last=False)
        logging.info("User {} claimed client {}.".format(user, client_id))
        return client_id

    def remove(self, user: str, client_id: str):
        """Removes a client registration from the vpn server."""
        try:
            if client_id.endswith('.ovpn'):
                client_id = client_id[:-len('.ovpn')]
            client_index = self.clients.index(client_id) + 1
        except ValueError:
            raise RuntimeError("Client {} not found".format(client_id))
        output = subprocess.run(
            [self.program, 'revoke', str(client_index)])
        if output.returncode != 0:
            # Log the error.
            logging.error("{} exitted with status code {} while revoking client {}.".format(
                self.program, output.returncode, client_id))
            raise RuntimeError(
                "Couldn't remove client {}. Contact the vpn server admin.".format(client_id))
        self.client_count -= 1
        self.clients.remove(client_id)
        self.user_clients_map[user].remove(client_id)
        logging.info("User {} deleted client {}.".format(user, client_id))

    def pickle(self, path: str):
        if os.path.exists(path):
            # Backup; just incase something goes wrong, or if a pickle is interrupted.
            root, ext = os.path.splitext(path)
            backup = root + '_backup' + ext
            shutil.copy(path, backup)
        pickle.dump(self, open(path, 'wb'))

    @staticmethod
    def unpickle(path: str) -> 'VPNManager':
        return pickle.load(open(path, 'rb'))

    @staticmethod
    def purge(purger_program_path: str):
        while subprocess.run([purger_program_path, 'revoke', '1']).returncode == 0:
            pass
        logging.info("Finished purging the server's clients.")

    def list_ips(self):
        """Prints a json object to stdout listing IP-clients relation."""
        print('{')
        for ip, clients in self.user_clients_map.items():
            print('\t', ip, ': [', sep='')
            for client in clients:
                print('\t\t', client, ',', sep='')
            print('\t', '],', sep='')
        print('}')
