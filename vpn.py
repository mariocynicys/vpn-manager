#!/usr/bin/env python3
"""
A server to add and remove OpenVPN clients, fully accessible by external users.
Exposes a port which users can hit to request/delete openVPN clients.

WARNING: You shouldn't have other than one instance of this server running on a machine.
If two or more instances are used in the same machine, one instance WILL WRONGFULLY DELETE
the clients created by another.
"""

import os
import signal
import logging
import argparse
import threading
from typing import List
from http.server import ThreadingHTTPServer

from vpn_manager import VPNManager
from vpn_request_handler import VPNRequestHandler


DRIVER_PROGRAM = "./client.sh"
"""The driver program that handles creating and revoking clients."""

PICKLE_EVERY = 10 * 60
"""The number of seconds after which the vpn manager will get pickled, periodically."""

UNBLOCK_IPS_EVERY = 24 * 60 * 60
"""The number of seconds after which service denied IP addresses can use the service again."""

MAX_CLIENTS_PER_USER = 10
"""The maximum nubmer of clients a single user (IP) can own at the same time."""

MAX_INMEMORY_OVPN_FILE_COUNT = 500
"""The maximum number of ovpn file to cache in memory."""


class CustomArgParseFormatter(
        argparse.ArgumentDefaultsHelpFormatter,
        argparse.RawDescriptionHelpFormatter):
    """A custom formatter that combines the features of multiple base classes.

    This gives us defaults for each argument in the help text, plus it preserves
    whitespace in the description field.

    Credits: https://github.com/shaka-project/shaka-streamer/blob/4d1341df12309d179d067dc9bf634dc3f7a7c865/shaka-streamer#L36-L44
    """
    pass


def job(action, period: float, shutdown: threading.Event, *args, **kwargs):
    """A function that calls `action` with `args` and `kwargs` every `period`
    with a `shutdown` event. `action` is called one last time after `shutdown` is set."""
    while not shutdown.is_set():
        shutdown.wait(period)
        logging.info("Running the periodic job: {} with args {} and kwargs {}".format(
            action.__name__, args, kwargs))
        action(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=CustomArgParseFormatter)
    parser.add_argument('-f', '--from-pickle', dest='picklefile',
                        help='The path to the pickled vpn manager to use.',
                        default='pickled_vpn_manager.pickle')
    parser.add_argument('-p', '--port', type=int,
                        help='The port this service runs on.',
                        default=8000)
    parser.add_argument('-m', '--max-clients', type=int, dest='maxclientcount',
                        help='The maximum number of clients the service can handle.',
                        default=10000)
    parser.add_argument('-l', '--log-to', dest='logfile',
                        help='A file to log to. The logger will always append'
                             ' to that file and won\'t overwrite it.'
                             ' Use "-" to log to stderr.',
                        default='debug.log')
    parser.add_argument('-u', '--list-users',
                        action='store_true',
                        help='List the users (IPs) and the clients they own.'
                             ' This doesn\'t start the server.')
    parser.add_argument('--purge',
                        action='store_true',
                        help='Unregisters all the clients.'
                             ' This option will invalidate any pickled vpn manager'
                             ' and you will need to get a new one the next time.'
                             ' This doesn\'t start the server.')
    args = parser.parse_args()

    # If the log file is '-', log to stderr.
    if args.logfile == '-':
        args.logfile = None

    # Initialize a global logger.
    logging.basicConfig(filename=args.logfile, level=logging.NOTSET,
                        format="%(levelname)s::%(asctime)s: %(message)s",
                        datefmt="[%a %b %d %Y %H:%M:%S %zUTC]")

    # If purging is specified, delete clients from that index mark and exit.
    if args.purge:
        VPNManager.purge(DRIVER_PROGRAM)
        return

    # If list users is specified, list the users and exit.
    if args.list_users:
        try:
            VPNManager.unpickle(args.picklefile).list_ips()
        except Exception:
            print(("ERROR: Couldn't unpickle {}. Make sure that you pass a '-f PICKLEFILE' "
                   "of a valid vpn manager to get the users list from.").format(args.picklefile))
        return

    # Get a vpn manager. Either from the disk or a fresh one.
    if os.path.exists(args.picklefile):
        vpn_manager = VPNManager.unpickle(args.picklefile)
    else:
        logging.info(
            "{} doesn't exist, creating a fresh vpn manager".format(args.picklefile))
        vpn_manager = VPNManager()

    # Patch the vpn manager with the current settings.
    vpn_manager.program = DRIVER_PROGRAM
    vpn_manager.max_client_count = args.maxclientcount
    vpn_manager.max_clients_per_user = MAX_CLIENTS_PER_USER
    vpn_manager.max_cache_size = MAX_INMEMORY_OVPN_FILE_COUNT

    # Initialize a server.
    server = ThreadingHTTPServer(('0.0.0.0', args.port),
                                 lambda *args, **kwargs: VPNRequestHandler(vpn_manager, *args, **kwargs))

    # Prepare a thread to run the server.
    threads: List[threading.Thread] = []
    threads.append(threading.Thread(
        name='vpn request handler', target=server.serve_forever))

    # Register the signal handlers.
    shutdown_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: shutdown_event.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown_event.set())

    # Add a pickler job.
    threads.append(threading.Thread(
        name='pickler', target=job, args=(vpn_manager.pickle, PICKLE_EVERY, shutdown_event, args.picklefile)))

    # Add an ip table cache clean job.
    threads.append(threading.Thread(
        name='ip table cache clean', target=job, args=(VPNRequestHandler.clear_ip_table, UNBLOCK_IPS_EVERY, shutdown_event)))

    # Start the threads.
    for thread in threads:
        thread.start()

    # Hold the main thread until we get a shutdown signal.
    logging.info("Service started.")
    shutdown_event.wait()

    # Shutdown the server and join the server thread.
    logging.info("Shutting down.")
    server.shutdown()
    for thread in threads:
        thread.join()


if __name__ == '__main__':
    main()
