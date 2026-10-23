from dataclasses import dataclass
from urllib.parse import quote


@dataclass
class ProxyConfig:
    host: str = "server.paedml-linux.lokal"
    port: int = 3128
    scheme: str = "http"
    needs_auth: bool = True
    bypass_proxy: bool = False

    def build_url(self, username: str = "", password: str = "") -> str:
        if self.scheme.lower() not in ("http", "https"):
            raise ValueError(f"{self.scheme} is currently not supported, only http and https are allowed.")

        if not self.bypass_proxy and (not self.host or not 1 <= self.port <= 65535):
            raise ValueError("Invalid proxy address or port.")

        if self.needs_auth:
            if not username or not password:
                raise ValueError("Credentials are required")
            username = quote(username, safe="")
            password = quote(password, safe="")
            auth = f"{username}:{password}@"
        else:
            auth = ""

        return f"{self.scheme}://{auth}{self.host}:{self.port}"