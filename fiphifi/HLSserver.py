import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__package__ + '.hls')

class HLSHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, buffer_manager=None, **kwargs):
        self.buffer_manager = buffer_manager
        super().__init__(*args, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/stream.m3u8':
            self._serve_playlist()
        elif path.startswith('/segments/'):
            self._serve_segment(path[9:])  # Strip /segments/
        else:
            self.send_error(404)

    def _serve_playlist(self):
        segments = sorted(os.listdir(self.buffer_manager.dldir))
        if not segments:
            self.send_error(404)
            return

        playlist = '#EXTM3U\n'
        playlist += '#EXT-X-VERSION:3\n'
        playlist += f'#EXT-X-TARGETDURATION:{self.buffer_manager.duration}\n'
        playlist += f'#EXT-X-MEDIA-SEQUENCE:{len(segments)}\n'

        for segment in segments[-5:]:  # Keep a rolling window
            playlist += f'#EXTINF:{self.buffer_manager.duration},\n'
            playlist += f'/segments/{segment}\n'

        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
        self.end_headers()
        self.wfile.write(playlist.encode())

    def _serve_segment(self, segment_name):
        segment_path = os.path.join(self.buffer_manager.dldir, segment_name)
        
        if not os.path.exists(segment_path):
            self.send_error(404)
            return

        with open(segment_path, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', 'video/MP2T')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

class HLSServer(threading.Thread):
    def __init__(self, buffer_manager, port=8080):
        super().__init__()
        self.buffer_manager = buffer_manager
        self.port = port
        self.server = None

    def run(self):
        handler = lambda *args, **kwargs: HLSHandler(*args, buffer_manager=self.buffer_manager, **kwargs)
        self.server = HTTPServer(('', self.port), handler)
        logger.info(f'Starting HLS server on port {self.port}')
        self.server.serve_forever()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()