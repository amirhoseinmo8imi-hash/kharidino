"""Embedded Flask server for Kharidino Android. Binds to loopback only."""
import os
import sys
import threading
from pathlib import Path
from werkzeug.serving import make_server

_server = None
_thread = None


def start(app_root: str, port: int = 8765):
    global _server, _thread
    if _server is not None:
        return "http://127.0.0.1:%s/" % port

    root = Path(app_root).resolve()
    if not (root / "app.py").is_file():
        raise RuntimeError("فایل اصلی سایت خریدینو در بسته برنامه پیدا نشد.")

    os.environ["KHARIDINO_ANDROID_LOCAL"] = "1"
    os.environ["FLASK_DEBUG"] = "0"
    sys.path.insert(0, str(root))
    os.chdir(str(root))

    import app as kharidino_app
    kharidino_app.app.config["KHARIDINO_ANDROID_LOCAL"] = True

    _server = make_server("127.0.0.1", int(port), kharidino_app.app, threaded=True)
    _thread = threading.Thread(target=_server.serve_forever, name="KharidinoLocalHost", daemon=True)
    _thread.start()
    return "http://127.0.0.1:%s/" % port


def stop():
    global _server, _thread
    if _server is not None:
        _server.shutdown()
        _server = None
        _thread = None
