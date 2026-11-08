#!/usr/bin/env python3
"""Chạy thử app điện thoại ngay trên máy tính (không cần Colab, không cần GPU).

    python3 mobile/serve.py --mock          # giao diện + Forge giả để xem trước
    python3 mobile/serve.py                 # dùng Forge thật ở http://127.0.0.1:7860
    python3 mobile/serve.py --forge https://xxxx.gradio.live --port 8787

Vì sao cần proxy: trang do server này phục vụ ở `http://<ip-máy-tính>:8787`, còn Forge
ở cổng khác — gọi thẳng sẽ vướng CORS. Server này chuyển tiếp `/sdapi/*` sang Forge
nên điện thoại trong cùng Wi-Fi chỉ cần mở `http://<ip-máy-tính>:8787`.

`--mock` dựng Forge giả: có tiến trình tăng dần, có Huỷ, trả ảnh gradient PNG để kiểm
tra toàn bộ luồng UI mà không tốn một giây GPU.
"""

import argparse
import base64
import json
import math
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import zlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent / "app"
PROXY_PREFIXES = ("/sdapi/", "/internal/")
LONG_TIMEOUT = 3600


# --------------------------------------------------------------------- PNG giả
def _png(width, height, pixel):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel(x, y))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


def _hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return int(r * 255), int(g * 255), int(b * 255)


def demo_png(width, height, hue):
    """Ảnh gradient + vầng sáng, đủ để thấy bố cục dọc/ngang đúng."""
    cx, cy = width * 0.5, height * 0.42
    radius = min(width, height) * 0.42

    def pixel(x, y):
        t = (x / width + y / height) / 2
        base = _hsv((hue + t * 0.12) % 1.0, 0.62, 0.32 + t * 0.35)
        distance = math.hypot(x - cx, y - cy)
        glow = max(0.0, 1.0 - distance / radius) ** 2
        colour = [min(255, int(c + glow * 210)) for c in base]
        return (*colour, 255)

    return _png(width, height, pixel)


# --------------------------------------------------------------------- Forge giả
class MockForge:
    """Đủ endpoint để UI chạy thật: options, cmd-flags, progress, interrupt, txt2img."""

    def __init__(self):
        self.lock = threading.Lock()
        self.started = 0.0
        self.duration = 6.0
        self.steps = 25
        self.job = ''
        self.seed = 123456789

    def begin(self, payload):
        with self.lock:
            self.started = time.time()
            self.steps = int(payload.get("steps") or 25)
            self.duration = max(2.0, self.steps * 0.24)
            self.job = payload.get("prompt", '')[:60]

    def progress(self):
        with self.lock:
            if not self.started:
                return {"progress": 0.0, "eta_relative": 0.0,
                        "state": {"sampling_step": 0, "sampling_steps": self.steps,
                                  "job": "", "job_count": 0}, "current_image": None}
            elapsed = time.time() - self.started
            ratio = min(1.0, elapsed / self.duration)
            return {
                "progress": 0.0 if ratio >= 1 else ratio,
                "eta_relative": max(0.0, self.duration - elapsed),
                "state": {"sampling_step": int(ratio * self.steps),
                          "sampling_steps": self.steps, "job": self.job,
                          "job_count": 0 if ratio >= 1 else 1},
                "current_image": None,
            }

    def interrupt(self):
        with self.lock:
            self.started = 0.0
            self.job = ''

    def render(self, payload):
        width = int(payload.get("width") or 1024)
        height = int(payload.get("height") or 1344)
        seed = payload.get("seed")
        if seed in (None, -1, '-1'):
            seed = int(time.time()) % 1000000000
        scale = 0.5 if width * height > 1_200_000 else 1.0
        image = demo_png(max(256, int(width * scale)), max(256, int(height * scale)),
                         (int(seed) % 97) / 97)
        info = {
            "seed": int(seed),
            "width": width,
            "height": height,
            "steps": int(payload.get("steps") or 25),
            "sampler_name": payload.get("sampler_name") or 'Euler a',
            "cfg_scale": payload.get("cfg_scale") or 6,
            "prompt": payload.get("prompt", ''),
            "negative_prompt": payload.get("negative_prompt", ''),
            "mock": True,
        }
        return {"images": [base64.b64encode(image).decode()],
                "info": json.dumps(info), "parameters": payload}


MOCK = MockForge()


# --------------------------------------------------------------------- handler
class Handler(SimpleHTTPRequestHandler):
    forge = "http://127.0.0.1:7860"
    mock = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    # ---------------------------------------------------------------- tiện ích
    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(length) if length else b''

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[app] {self.address_string()} {fmt % args}\n")

    # ---------------------------------------------------------------- route
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.end_headers()

    def do_GET(self):
        if any(self.path.startswith(prefix) for prefix in PROXY_PREFIXES):
            return self._proxy('GET')
        return super().do_GET()

    def do_POST(self):
        if any(self.path.startswith(prefix) for prefix in PROXY_PREFIXES):
            return self._proxy('POST')
        self.send_error(404)

    # ---------------------------------------------------------------- proxy
    def _proxy(self, method):
        body = self._body() if method == 'POST' else None
        if self.mock:
            return self._mock(method, body)
        url = f"{self.forge}{self.path}"
        headers = {'Content-Type': self.headers.get('Content-Type', 'application/json')}
        if self.headers.get('Authorization'):
            headers['Authorization'] = self.headers['Authorization']
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=LONG_TIMEOUT) as response:
                payload = response.read()
                self.send_response(response.status)
                self.send_header('Content-Type',
                                 response.headers.get('Content-Type', 'application/json'))
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as error:
            payload = error.read()
            self._json({'error': payload.decode('utf-8', 'replace')[:800]}, error.code)
        except Exception as error:                       # noqa: BLE001
            self._json({'error': f'Không gọi được Forge: {error}'}, 502)

    def _mock(self, method, body):
        path = self.path.split('?', 1)[0]
        payload = json.loads(body.decode() or '{}') if body else {}
        if path == '/sdapi/v1/options':
            return self._json({'sd_model_checkpoint': 'waiIllustriousSDXL_v170 (mock)',
                               'sd_vae': 'Automatic', 'CLIP_stop_at_last_layers': 2})
        if path == '/sdapi/v1/cmd-flags':
            return self._json({'api': True, 'port': 7860, 'listen': True, 'mock': True})
        # Giống Forge thật: API chuẩn đọc bằng GET, route nội bộ chỉ nhận POST.
        if path == '/internal/progress' and method != 'POST':
            return self._json({'detail': 'Method Not Allowed'}, 405)
        if path == '/sdapi/v1/progress' and method != 'GET':
            return self._json({'detail': 'Method Not Allowed'}, 405)
        if path in ('/sdapi/v1/progress', '/internal/progress'):
            return self._json(MOCK.progress())
        if path == '/sdapi/v1/interrupt':
            MOCK.interrupt()
            return self._json({})
        if path == '/sdapi/v1/samplers':
            names = ['Euler a', 'Euler', 'DPM++ 2M', 'DPM++ 2M SDE', 'UniPC', 'LCM']
            return self._json([{'name': name, 'aliases': [], 'options': {}} for name in names])
        if path == '/sdapi/v1/upscalers':
            return self._json([{'name': name} for name in
                               ('RealESRGAN_x4plus_anime_6B', 'R-ESRGAN 4x+', 'Latent')])
        if path == '/sdapi/v1/txt2img':
            MOCK.begin(payload)
            deadline = time.time() + MOCK.duration
            while time.time() < deadline and MOCK.started:
                time.sleep(0.2)          # nghỉ để tiến trình được đọc song song
            if not MOCK.started:         # đã bị Huỷ
                MOCK.started = 0.0
                return self._json({'error': 'interrupted'}, 499)
            result = MOCK.render(payload)
            MOCK.started = 0.0
            return self._json(result)
        if path == '/sdapi/v1/sd-models':
            return self._json([{'title': 'waiIllustriousSDXL_v170.safetensors',
                                'model_name': 'waiIllustriousSDXL_v170'}])
        return self._json({'error': 'mock: endpoint chưa hỗ trợ'}, 404)


def lan_ip():
    """IP trong Wi-Fi để mở app từ điện thoại (không cần internet)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('8.8.8.8', 80))
            return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Chạy app điện thoại ở máy tính.')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--forge', default='http://127.0.0.1:7860',
                        help='địa chỉ Forge để chuyển tiếp /sdapi (mặc định cổng 7860)')
    parser.add_argument('--mock', action='store_true',
                        help='dựng Forge giả để xem trước giao diện, không cần GPU')
    args = parser.parse_args(argv)

    if not (APP_DIR / 'index.html').is_file():
        print(f'❌ Không thấy {APP_DIR / "index.html"}', file=sys.stderr)
        return 2
    if not (APP_DIR / 'data' / 'tags.json').is_file():
        print('⚠️ Chưa có mobile/app/data/tags.json — chạy: python3 mobile/build_data.py',
              file=sys.stderr)

    Handler.forge = args.forge.rstrip('/')
    Handler.mock = args.mock
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    mode = 'MOCK (Forge giả)' if args.mock else f'proxy → {Handler.forge}'
    print(f'📱 App điện thoại: http://127.0.0.1:{args.port}  ·  {mode}')
    print(f'   Từ điện thoại cùng Wi-Fi: http://{lan_ip()}:{args.port}')
    print('   Ctrl+C để dừng.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nDừng server.')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
