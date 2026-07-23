"""Threaded wsgiref launcher for the Django dashboard, with optional HTTP Basic Auth.

The dashboard has no application-level login. When DASHBOARD_USER and DASHBOARD_PASSWORD are
set, every request must carry HTTP Basic credentials — this is what makes it safe to expose the
port beyond localhost. With the variables unset the server runs unprotected, which is only
appropriate on 127.0.0.1.
"""
import base64
import hmac
import os
import sys
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIServer

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()
from config.wsgi import application


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class BasicAuth:
    """Gate every request behind HTTP Basic credentials (constant-time comparison)."""

    def __init__(self, app, user, password, realm="Fuel Demand Dashboard"):
        self.app, self.user, self.password, self.realm = app, user, password, realm

    def _ok(self, header):
        if not header or not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
            user, _, password = decoded.partition(":")
        except Exception:
            return False
        # Compare both fields so a wrong username costs the same time as a wrong password.
        return (hmac.compare_digest(user, self.user)
                & hmac.compare_digest(password, self.password))

    def __call__(self, environ, start_response):
        if self._ok(environ.get("HTTP_AUTHORIZATION", "")):
            # Consume the header: otherwise DRF's BasicAuthentication tries to resolve these
            # credentials against the Django user table and rejects the request with 403.
            environ.pop("HTTP_AUTHORIZATION", None)
            return self.app(environ, start_response)
        start_response("401 Unauthorized",
                       [("WWW-Authenticate", f'Basic realm="{self.realm}", charset="UTF-8"'),
                        ("Content-Type", "text/plain; charset=utf-8")])
        return [b"Authentication required."]


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    host = os.environ.get("HOST", "127.0.0.1")

    app = application
    user, password = os.environ.get("DASHBOARD_USER"), os.environ.get("DASHBOARD_PASSWORD")
    if user and password:
        app = BasicAuth(app, user, password)
        auth_state = "Basic Auth ENABLED"
    else:
        auth_state = "Basic Auth DISABLED (no DASHBOARD_USER/DASHBOARD_PASSWORD)"
        if host != "127.0.0.1":
            print(f"WARNING: binding {host} without authentication — set DASHBOARD_USER and "
                  f"DASHBOARD_PASSWORD, or bind 127.0.0.1.", flush=True)

    httpd = make_server(host, port, app, server_class=ThreadingWSGIServer)
    print(f"Django serving on http://{host}:{port} — {auth_state}", flush=True)
    httpd.serve_forever()
