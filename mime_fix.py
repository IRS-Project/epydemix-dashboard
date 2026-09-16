# mime_fix.py
#
# Let Streamlit's static file server (server.enableStaticServing) serve ./static/
# HTML as a real, rendered page reachable by a relative URL (app/static/<file>.html).
#
# Two obstacles are handled:
#   1. On Windows the registry can map .html to text/plain -> register text/html.
#   2. Streamlit's AppStaticFileHandler force-serves any extension outside a small
#      media allowlist as text/plain (with nosniff). We add ".html" to that
#      allowlist so the correct Content-Type (text/html) is sent instead.
#
# The allowlist tuple is consulted per request, so patching it once (on app load,
# before the provenance link is clicked) is sufficient. Import this module from
# the app entry and from the References page.
import mimetypes

mimetypes.add_type("text/html", ".html")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

try:  # best-effort; never break the app if Streamlit internals move
    from streamlit.web.server import app_static_file_handler as _asf

    if ".html" not in _asf.SAFE_APP_STATIC_FILE_EXTENSIONS:
        _asf.SAFE_APP_STATIC_FILE_EXTENSIONS = (
            tuple(_asf.SAFE_APP_STATIC_FILE_EXTENSIONS) + (".html",)
        )
except Exception:
    pass
