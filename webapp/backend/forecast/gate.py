"""Session-based login gate for the dashboard.

A lightweight, real login page (not the browser Basic-Auth popup). Credentials come from
DASHBOARD_USER / DASHBOARD_PASSWORD in the environment. If DASHBOARD_PASSWORD is unset the gate
is disabled (open access) — appropriate only on localhost.
"""
import hmac
import os

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

USER = os.environ.get("DASHBOARD_USER", "")
PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
GATE_ON = bool(PASSWORD)
OPEN_PREFIXES = ("/login", "/logout")


class LoginRequiredMiddleware:
    """Redirect unauthenticated HTML requests to /login; return 401 JSON for the API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if GATE_ON and not request.session.get("auth"):
            p = request.path
            if not p.startswith(OPEN_PREFIXES):
                if p.startswith("/api/"):
                    return JsonResponse({"detail": "Authentication required"}, status=401)
                nxt = p if p != "/" else ""
                return redirect(f"/login{('?next=' + nxt) if nxt else ''}")
        return self.get_response(request)


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in · Fuel Demand Forecast</title>
<style>
  :root{{color-scheme:light dark}}
  *{{box-sizing:border-box}}
  body{{margin:0;min-height:100vh;display:grid;place-items:center;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    background:linear-gradient(135deg,#0b1220,#0f2038 60%,#0a2a1f);color:#e8eef7}}
  .card{{width:min(92vw,380px);background:#111a2e;border:1px solid #223049;border-radius:16px;padding:32px 28px;
    box-shadow:0 24px 60px rgba(0,0,0,.45)}}
  .brand{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
  .dot{{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#0a9c4a,#2563eb);display:grid;place-items:center;font-size:18px}}
  h1{{font-size:18px;margin:0}}
  .sub{{color:#8ea0bd;font-size:12.5px;margin:2px 0 22px}}
  label{{display:block;font-size:12px;color:#9fb0c9;margin:14px 0 6px}}
  input{{width:100%;padding:11px 12px;border-radius:9px;border:1px solid #2a3a55;background:#0c1526;color:#e8eef7;font-size:14px}}
  input:focus{{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.25)}}
  button{{width:100%;margin-top:22px;padding:12px;border:0;border-radius:9px;cursor:pointer;font-size:14px;font-weight:600;
    color:#fff;background:linear-gradient(135deg,#0a9c4a,#2563eb)}}
  button:hover{{filter:brightness(1.07)}}
  .err{{background:#3a1622;border:1px solid #7f1d33;color:#ffb3c4;font-size:12.5px;padding:9px 11px;border-radius:8px;margin-bottom:8px}}
  .foot{{margin-top:18px;text-align:center;font-size:11px;color:#6b7c98}}
</style></head><body>
  <form class="card" method="post" action="/login{next_qs}">
    <div class="brand"><div class="dot">⛽</div><h1>Fuel Demand Forecast</h1></div>
    <div class="sub">Cofano · demand forecasting dashboard</div>
    {error}
    <label>Username</label>
    <input name="username" autocomplete="username" autofocus>
    <label>Password</label>
    <input name="password" type="password" autocomplete="current-password">
    <button type="submit">Sign in</button>
    <div class="foot">Authorised access only</div>
  </form>
</body></html>"""

ERR_HTML = '<div class="err">Invalid username or password.</div>'


def _page(error="", next_val=""):
    qs = f"?next={next_val}" if next_val else ""
    return LOGIN_PAGE.format(error=(ERR_HTML if error else ""), next_qs=qs)


@csrf_exempt
def login_view(request):
    if not GATE_ON:
        return redirect("/")
    next_val = request.GET.get("next", "") or request.POST.get("next", "")
    if request.method == "POST":
        u = request.POST.get("username", "")
        pw = request.POST.get("password", "")
        if hmac.compare_digest(u, USER) & hmac.compare_digest(pw, PASSWORD):
            request.session["auth"] = True
            request.session.set_expiry(60 * 60 * 12)     # 12h
            return redirect(next_val or "/")
        return HttpResponse(_page(error=True, next_val=next_val), status=401)
    if request.session.get("auth"):
        return redirect(next_val or "/")
    return HttpResponse(_page(next_val=next_val))


def logout_view(request):
    request.session.flush()
    return redirect("/login")
