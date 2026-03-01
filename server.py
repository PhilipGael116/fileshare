import http.server
import socketserver
import os
import json
from urllib.parse import unquote

PORT = 8080
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class FilerHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_type = self.headers.get("Content-Type")
        content_length = int(self.headers.get("Content-Length", 0))

        # Extract boundary
        boundary = content_type.split("boundary=")[1].encode()

        # Read only the header part first (until we hit \r\n\r\n)
        raw_header = b""
        while b"\r\n\r\n" not in raw_header:
            raw_header += self.rfile.read(1)

        # Parse filename from header
        if b"filename=" not in raw_header:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No file received")
            return

        filename = raw_header.split(b"filename=")[1].split(b'"')[1].decode()
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Calculate how many bytes are actually file data
        # Subtract the header we already read + boundary + trailing bytes
        header_length = len(raw_header)
        # boundary line at start + "--" prefix + \r\n = len(boundary) + 4
        # trailing boundary "--" + boundary + "--\r\n" at end
        trailing = len(boundary) + 8
        file_length = content_length - header_length - trailing - len(boundary) - 4

        # Stream file in chunks
        CHUNK_SIZE = 1024 * 1024  # 1MB chunks
        bytes_remaining = file_length

        with open(filepath, "wb") as f:
            while bytes_remaining > 0:
                chunk_size = min(CHUNK_SIZE, bytes_remaining)
                chunk = self.rfile.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                bytes_remaining -= len(chunk)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"File uploaded successfully!")

def do_GET(self):
    if self.path == "/files":
        files = os.listdir(UPLOAD_FOLDER)
        response = json.dumps(files).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response)

    elif self.path.startswith("/uploads/"):
        filename = unquote(self.path[9:])  # Add unquote() here
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        if not os.path.exists(filepath):
            self.send_response(404)
            self.end_headers()
            return

        file_size = os.path.getsize(filepath)
        range_header = self.headers.get("Range")

        if range_header:
            # Parse range e.g "bytes=0-999"
            ranges = range_header.strip().replace("bytes=", "")
            start, end = ranges.split("-")
            start = int(start)
            end = int(end) if end else file_size - 1
            length = end - start + 1

            self.send_response(206)  # Partial content
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
    else:
        super().do_GET()

class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

with ThreadedServer(("", PORT), FilerHandler) as httpd:
    print(f"Server running on Port {PORT}")
    httpd.serve_forever()