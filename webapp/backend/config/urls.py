import os, mimetypes
from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse, Http404
from django.urls import path, re_path, include


def serve_frontend(request, path=""):
    """Phục vụ Next.js static export (frontend/out) trên cùng cổng với API."""
    base = str(settings.FRONTEND_OUT)
    if not os.path.isdir(base):
        return HttpResponse("Frontend chưa build. Chạy: cd frontend && npm run build",
                            content_type="text/plain", status=200)
    cand = os.path.normpath(os.path.join(base, path))
    if not cand.startswith(base):
        raise Http404
    for f in ([cand] if path else []) + ([cand + ".html"] if path else []) + [os.path.join(base, "index.html")]:
        if os.path.isfile(f):
            ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
            return FileResponse(open(f, "rb"), content_type=ctype)
    raise Http404


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("forecast.urls")),
    re_path(r"^(?P<path>.*)$", serve_frontend),
]
