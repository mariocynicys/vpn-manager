import logging
from typing import Dict
from collections import defaultdict

from vpn_manager import VPNManager
from http.server import BaseHTTPRequestHandler


class VPNRequestHandler(BaseHTTPRequestHandler):
    """A request handler for the VPN service."""

    RESPONSE_ALREADY_SENT = 'RESPONSE_ALREADY_SENT'
    """A marker used to indicate that a response has already been sent."""

    MAX_REQUESTS_PER_HOUR = 1000
    """The maximum number of requests per hour before considering that user an abuser."""

    ip_table: Dict[str, int] = defaultdict(int)
    """A map IPs to how many times they have accessed the service. This cache doesn't get pickled."""

    def __init__(self, vpn_manager: VPNManager, *args, **kwargs):
        self.vpn_manager = vpn_manager
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """GET requests go here. Other request verbs don't get processed because they have no handlers."""
        self.log_request = lambda _: None
        # self.client_ip = self.client_address[0]
        # Using 'X-Real-IP' here instead because the app lives behind an Nginx reverse proxy.
        self.client_ip = self.headers['X-Real-IP']
        if self.check_denail():
            logging.info("Request #{} from {} has been denied. Was a GET {}".format(
                self.ip_table[self.client_ip], self.client_ip, self.path))
            return
        # Adding a '/about' is a fancy way of making requests going to '/' get handled by '/about' handler.
        command = (self.path + '/about').replace('/', ' ').split()[0]
        handler = type(self).__dict__.get('handle_route_' + command)
        if handler is None:
            code, body = self.handle_route_404()
        else:
            code, body = handler(self)

        # The following block might fail if the designated handler has already sent a response.
        if body != self.RESPONSE_ALREADY_SENT:
            # Send the response code and the response headers.
            self.send_response(code)
            self.end_headers()
            # Send the response body.
            self.wfile.write(bytes(body, 'utf-8'))

        # Log that request.
        logging.info(
            "Got GET {} from {} - returned {}".format(self.path, self.client_ip, code))

    def handle_route_new(self):
        try:
            id = self.vpn_manager.new(self.client_ip)
            filename = id + '.ovpn'
            return (200,
                    "<p>Generated an OpenVPN client for you. Click the link below to download it.</p>"
                    "<a href=/get/{} target=_blank>Download</a>"
                    "<p>Please keep the ovpn file name as is. The file name is the client ID. "
                    "You can use it to delete this client when you no longer need it (by hitting /delete/CLIENT-ID).</p>".format(filename))
        except Exception as e:
            return (400, str(e))

    def handle_route_get(self):
        try:
            id = self.path.replace('/', ' ').split()[1][:-len('.ovpn')]
            ovpn = self.vpn_manager.cache[id]
            self.send_response(200)
            # This header will cause the file to be download directly and not displayed as html.
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(ovpn)
            # We have already sent a response.
            return (200, 'RESPONSE_ALREADY_SENT')
        except IndexError:
            return (400, "Please don't send GET /get requests by yourself.")
        except KeyError:
            return (500, "The server doesn't have that client file anymore.\n"
                         "If you have lost it, please delete it from the /delete endpoint.")
        except Exception as e:
            return (400, str(e))

    def handle_route_delete(self):
        try:
            client_id = self.path.replace('/', ' ').split()[1]
            self.vpn_manager.remove(self.client_ip, client_id)
            return (200, "{} was successfully removed, thanks!".format(client_id))
        except IndexError:
            return (400, "You need to provide a client ID for the client you want to delete. "
                         "The ID is the ovpn file name (which was downloaded from the /new endpoint).")
        except Exception as e:
            return (400, str(e))

    def handle_route_myip(self):
        return (200, self.client_ip)

    def handle_route_about(self):
        return (200, "<p>Visit <a href=https://github.com/meryacine/vpn-manager>Github</a></p>"
                     "<p>To get an OpenVPN client visit <a href=/new>new</a><p>"
                     "<p>To delete an OpenVPN client visit <a href=/delete>delete</a><p>"
                     "<p>To know your IP address visit <a href=/myip>myip</a><p>")

    def handle_route_404(self):
        hidden_endpoints = ['/get', '/404']
        endpoints = filter(lambda s: s.startswith('handle_route_'),
                           type(self).__dict__.keys())
        endpoints = map(lambda s: '/' + s[len('handle_route_'):], endpoints)
        endpoints = [*filter(lambda s: s not in hidden_endpoints, endpoints)]
        return (404, "{} is not a configured endpoint.\nTry one of {}".format(self.path, endpoints))

    def check_denail(self) -> bool:
        """Check whether we should deny servicing this request.
        Returns True when service is denied."""
        self.ip_table[self.client_ip] += 1
        # Keep sending this message for 10 requests past the max request limit.
        if self.ip_table[self.client_ip] in range(self.MAX_REQUESTS_PER_HOUR,
                                                  self.MAX_REQUESTS_PER_HOUR + 10):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Are you a bot?")
            return True
        # After that don't respond to that IP nomore.
        elif self.ip_table[self.client_ip] > self.MAX_REQUESTS_PER_HOUR:
            self.close_connection = True
            return True
        return False

    @classmethod
    def clear_ip_table(cls):
        """Clears the IP table cache."""
        cls.ip_table.clear()
