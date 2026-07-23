"""Phục vụ Django WSGI bằng wsgiref threaded (ổn định trong môi trường này)."""
import os, sys
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


if __name__ == "__main__":
    # Binds to localhost by default. Set HOST=0.0.0.0 only behind a reverse proxy / trusted network,
    # and set DJANGO_ALLOWED_HOSTS accordingly — the dashboard has no authentication.
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    host = os.environ.get("HOST", "127.0.0.1")
    httpd = make_server(host, port, application, server_class=ThreadingWSGIServer)
    print(f"Django serving on http://{host}:{port}", flush=True)
    httpd.serve_forever()
