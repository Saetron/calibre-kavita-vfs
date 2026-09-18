import io
import json
import unittest
from webui import WebUIHandler, start_webui_server
from vfs_state import state


class DummyRequest:
    def __init__(self, request_bytes: bytes):
        self.rfile = io.BytesIO(request_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self.rfile
        return self.wfile

    def sendall(self, data: bytes):
        self.wfile.write(data)


def execute_request(method: str, path: str, body: bytes = b"") -> tuple[int, dict, bytes]:
    req_data = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(body)}\r\n\r\n".encode("utf-8") + body
    req = DummyRequest(req_data)
    WebUIHandler(req, ("127.0.0.1", 12345), None)
    raw = req.wfile.getvalue()

    # Parse HTTP response
    header_part, _, body_part = raw.partition(b"\r\n\r\n")
    lines = header_part.decode("utf-8", errors="replace").split("\r\n")
    status_line = lines[0]
    status_code = int(status_line.split()[1])

    headers = {}
    for line in lines[1:]:
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k.lower()] = v

    return status_code, headers, body_part


class TestWebUI(unittest.TestCase):
    def test_get_dashboard_html(self):
        status, headers, body = execute_request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        html = body.decode("utf-8")
        self.assertIn("Kavita VFS Dashboard", html)
        self.assertIn("function fetchStatus()", html)
        self.assertIn("function fetchBooks()", html)
        self.assertIn("function goToPage(", html)

    def test_get_api_status(self):
        status, headers, body = execute_request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body.decode("utf-8"))
        self.assertIn("total_books", data)
        self.assertIn("total_volumes", data)
        self.assertIn("total_chapters", data)
        self.assertIn("collision_count", data)

    def test_get_api_books(self):
        status, headers, body = execute_request("GET", "/api/books?q=test&limit=10&offset=5")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(data["offset"], 5)

    def test_post_api_sync(self):
        sync_called = False

        def on_sync():
            nonlocal sync_called
            sync_called = True

        WebUIHandler.trigger_sync_callback = on_sync
        status, headers, body = execute_request("POST", "/api/sync")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "sync_triggered")
        self.assertTrue(sync_called)

    def test_post_api_cleanup(self):
        cleanup_called = False

        def on_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
            return {"status": "cleanup_completed", "removed_count": 5, "empty_dirs_removed": 2}

        WebUIHandler.trigger_cleanup_callback = on_cleanup
        status, headers, body = execute_request("POST", "/api/cleanup")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "cleanup_completed")
        self.assertEqual(data["removed_count"], 5)
        self.assertTrue(cleanup_called)

    def test_not_found(self):
        status, headers, body = execute_request("GET", "/unknown_route")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
