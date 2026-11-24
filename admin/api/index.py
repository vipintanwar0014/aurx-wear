import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app as fastapi_app

class VercelPathMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")
            if not matched_path:
                matched_path = headers.get(b"x-forwarded-uri", b"").decode("utf-8")
            
            # If Vercel edge passed /404 or an internal rewrite path, ignore it and default to /
            if matched_path and matched_path not in ("/404", "/api/index.py", "/api/index") and not matched_path.startswith("/api/index"):
                scope["path"] = matched_path
            else:
                path = scope.get("path", "")
                if path.startswith("/api/index.py"):
                    scope["path"] = path[len("/api/index.py"):] or "/"
                elif path.startswith("/api/index"):
                    scope["path"] = path[len("/api/index"):] or "/"
                elif path in ("/api", "/404"):
                    scope["path"] = "/"
                elif path.startswith("/api/"):
                    if not path.startswith("/api/track-lead"):
                        scope["path"] = path[4:] or "/"

        await self.app(scope, receive, send)

app = VercelPathMiddleware(fastapi_app)
