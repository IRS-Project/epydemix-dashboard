# sitecustomize.py — auto-imported by Python's `site` at interpreter startup when
# this directory is on sys.path (Streamlit runs from the repo root). Registers the
# correct static MIME types at server-boot, so Streamlit's static file server
# serves ./static/*.html as text/html even on Windows, where the registry can
# otherwise map .html to text/plain. This makes the relative-URL provenance link
# on the Model References page open as a rendered page rather than raw source.
import mimetypes

mimetypes.add_type("text/html", ".html")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
