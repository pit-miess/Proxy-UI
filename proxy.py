from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import select
import socket
import requests
from urllib.parse import urlsplit
from config import ProxyConfig
SERVICE = "proxy_chain_app"

HOST = "server.paedml-linux.lokal"
PORT = 3128

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 3128

SCHEME = "http"
NEEDS_AUTH = True  # default: True

#DEBUG ONLY
BYPASS_PROXY = False # default: False


config = ProxyConfig(
    host=HOST,
    port=PORT,
    scheme=SCHEME,
    needs_auth=NEEDS_AUTH,
)


def remove_hop_headers(headers):
    blocked = {
        "connection",
        "proxy-connection",
        "proxy-authorization",
        "proxy-authenticate",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
    }

    connection_value = headers.get("Connection", "")
    blocked.update(
        item.strip().lower()
        for item in connection_value.split(",")
        if item.strip()
    )

    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in blocked
    }


class ForwardProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(f"Local proxy: {self.command} request")

    def finish_response(self):
        self.close_connection = True

    def do_CONNECT(self):
        """Handle HTTPS CONNECT tunnels."""
        upstream = None
        established = False

        try:
            target = self.path

            if (
                not target
                or "/" in target
                or "@" in target
                or "\r" in target
                or "\n" in target
            ):
                self.send_error(400, "Invalid CONNECT target")
                return

            parsed = urlsplit("//" + target)

            if not parsed.hostname or parsed.port is None:
                self.send_error(400, "Expected hostname:port")
                return

            if BYPASS_PROXY: # bypass for debugging
                upstream = socket.create_connection(
                    (parsed.hostname, parsed.port),
                    timeout=15,
                )
                upstream.settimeout(None)

            else:
                upstream = socket.create_connection(
                    (HOST, PORT),
                    timeout=15,
                )
                upstream.settimeout(None)

                username = self.server.username or ""
                password = self.server.password or ""

                raw_credentials = f"{username}:{password}".encode("utf-8")
                auth = base64.b64encode(raw_credentials).decode("ascii")

                connect_request = (
                    f"CONNECT {target} HTTP/1.1\r\n"
                    f"Host: {target}\r\n"
                    f"Proxy-Authorization: Basic {auth}\r\n"
                    "Proxy-Connection: Keep-Alive\r\n"
                    "\r\n"
                )

                upstream.sendall(connect_request.encode("ascii"))

                response_bytes = bytearray()

                while not response_bytes.endswith(b"\r\n\r\n"):
                    chunk = upstream.recv(1)
                    if not chunk:
                        raise ConnectionError("Upstream closed during CONNECT")

                    response_bytes.extend(chunk)

                    if len(response_bytes) > 65536:
                        raise ConnectionError("Upstream headers too large")

                status_line = bytes(response_bytes).split(b"\r\n", 1)[0]
                parts = status_line.split()

                if len(parts) < 2 or not parts[1].isdigit():
                    raise ConnectionError("Invalid upstream response")

                status_code = int(parts[1])

                if status_code != 200:
                    self.send_error(
                        502,
                        f"Upstream proxy rejected CONNECT ({status_code})",
                    )
                    return

            # Tell the client the tunnel is ready.
            self.connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            established = True

            # Relay encrypted TLS traffic in both directions.
            sockets = [self.connection, upstream]

            while True:
                readable, _, exceptional = select.select(
                    sockets, [], sockets, 60
                )

                if exceptional or not readable:
                    break

                for source in readable:
                    data = source.recv(65536)

                    if not data:
                        return

                    destination = (
                        upstream
                        if source is self.connection
                        else self.connection
                    )

                    destination.sendall(data)

        except (OSError, ValueError, ConnectionError) as exc:
            print(f"CONNECT error: {type(exc).__name__}: {exc}")

            if not established:
                try:
                    self.send_error(502, "Upstream tunnel failed")
                except OSError:
                    pass

        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass

            self.close_connection = True


    def do_GET(self):
        self.forward_http()

    def do_HEAD(self):
        self.forward_http()

    def do_POST(self):
        self.forward_http()

    def do_PUT(self):
        self.forward_http()

    def do_PATCH(self):
        self.forward_http()

    def do_DELETE(self):
        self.forward_http()

    def do_OPTIONS(self):
        self.forward_http()

    
    def forward_http(self):
        if not self.path.startswith(("http://", "https://")):
            self.send_error(400, "Expected an absolute URL")
            return

        response = None

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 10_000_000:
                self.send_error(413, "Request body too large")
                return

            body = self.rfile.read(length) if length else None
            headers = remove_hop_headers(self.headers)

            proxy_url = config.build_url(
                self.server.username,
                self.server.password,
            )

            response = requests.request(
                method=self.command,
                url=self.path,
                headers=headers,
                data=body,
                proxies={
                    "http": proxy_url,
                    "https": proxy_url,
                } if not BYPASS_PROXY else None,
                stream=True,
                allow_redirects=False,
                timeout=(15, 30),
            )

            self.send_response(response.status_code)

            skip_headers = {
                "content-length",
                "content-encoding",
                "transfer-encoding",
                "connection",
                "proxy-connection",
                "keep-alive",
                "proxy-authenticate",
                "proxy-authorization",
                "trailer",
                "upgrade",
            }

            for key, value in response.headers.items():
                if key.lower() not in skip_headers:
                    self.send_header(key, value)

            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            sent = 0
            if self.command != "HEAD" and response.status_code not in (204, 304):
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        self.wfile.write(chunk)
                        sent += len(chunk)

            self.wfile.flush()
            print(f"Upstream status: {response.status_code}; body bytes sent: {sent}")

        except (requests.RequestException, OSError, ValueError) as exc:
            print(f"HTTP forwarding error: {type(exc).__name__}: {exc}")
            self.close_connection = True

        finally:
            if response is not None:
                response.close()


class LocalProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, username, password):
        super().__init__(address, ForwardProxyHandler)
        self.username = username
        self.password = password
