"""Gradio 4.40 thật, SQLite/PNG fixture; không Forge/Torch/GPU hoặc dữ liệu cá nhân."""
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
import gradio as gr
from fastapi.testclient import TestClient
from gradio.routes import App
from PIL import Image, PngImagePlugin
from prompt_lib.history import ImageHistory
from prompt_lib.history_ui import HistoryPanel


class HistoryUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wai-history-ui-")
        self.root = Path(self.tmp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.store = ImageHistory([self.output], self.root / "cache")
        self.path = self.output / "sample.png"
        info = PngImagePlugin.PngInfo()
        info.add_text("parameters", "PRIVATE-PROMPT\nNegative prompt: private\nSteps: 25, Seed: 42, Size: 24x32")
        with Image.new("RGB", (24, 32), "#bad2e1") as image:
            image.save(self.path, pnginfo=info)
        self.original_bytes = self.path.read_bytes()
        with gr.Blocks(analytics_enabled=False) as self.demo:
            seed = gr.Number(value=-1, precision=0)
            self.panel = HistoryPanel(lambda: self.store, seed)

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_components_lazy_no_gpu_and_state_bounded(self):
        self.assertFalse(self.store.db_path.exists())
        components = self.demo.get_config_file()["components"]
        self.assertTrue(any(c["props"].get("label", "").startswith("Bảng ảnh đã tạo") for c in components))
        self.assertEqual(self.panel.ids.value, [])
        data = self.panel.refresh(12)
        self.assertEqual(len(data), 9)
        self.assertEqual(len(data[0]), 1)
        self.assertEqual(len(data[1][0]), 5)
        self.assertIsInstance(data[0][0][0], str)
        self.assertTrue(all(type(x) is int for x in data[2]))
        self.assertLess(len(json.dumps(data[2])), 512)
        self.assertNotIn("PRIVATE-PROMPT", json.dumps(data[:5]))
        self.assertFalse(any(isinstance(value, Image.Image) for value in data))

    def test_02_gallery_and_table_selection_original_download_seed(self):
        ids = self.panel.refresh()[2]
        for index in (0, [0, 1]):
            evt = gr.SelectData(None, {"index": index, "value": "unused"})
            selected_id, original, download, note = self.panel.select(ids, evt)
            self.assertEqual(original, str(self.path))
            self.assertEqual(download, original)
            self.assertIn("42", note)
            self.assertEqual(self.panel.use_seed(selected_id)[0], 42)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_03_invalid_missing_grid_seed_keeps_current_seed(self):
        ids = self.panel.refresh()[2]
        for index in (-1, 9999, None, True):
            evt = gr.SelectData(None, {"index": index, "value": None})
            self.assertIsNone(self.panel.select(ids, evt)[0])
        with self.path.open("wb") as stream:
            stream.write(b"changed")
        evt = gr.SelectData(None, {"index": 0, "value": None})
        self.assertIsNone(self.panel.select(ids, evt)[0])
        self.assertEqual(self.panel.use_seed(ids[0])[0], gr.skip())
        self.assertEqual(self.panel.use_seed(None)[0], gr.skip())

    def test_04_paging_and_refresh_only_metadata_no_image_accumulation(self):
        for i in range(26):
            with Image.new("RGB", (8, 8), "white") as image:
                image.save(self.output / f"{i}.png")
        for _ in range(3):
            values = self.panel.refresh(12)
            self.assertEqual(len(values[2]), 12)
            self.assertEqual(len(values[0]), 12)
        page2 = self.panel.next(1, 12)
        self.assertEqual(page2[3], 2)
        self.assertIsNone(page2[5])
        self.assertIsNone(page2[6])
        self.assertEqual(self.panel.previous(2, 12)[3], 1)
        self.assertEqual(len(self.panel.first_page(24)[2]), 24)
        self.assertEqual(self.panel._size(100000), 12)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_05_backend_failure_safe_no_body_or_prompt_dump(self):
        with patch.object(self.store, 'refresh', side_effect=OSError('PRIVATE-ERROR-AND-PROMPT')):
            result = self.panel.refresh()
        self.assertEqual(len(result), 9)
        self.assertNotIn('PRIVATE', repr(result))

    def test_06_real_http_callbacks_and_original_bytes(self):
        # Callback Gradio thật + session State: không giả lập postprocess/gallery/file.
        with TestClient(App.create_app(self.demo), raise_server_exceptions=True) as client:
            self.assertEqual(client.get('/config').status_code, 200)
            self.assertEqual(client.get('/info?all_endpoints=True').status_code, 200)
            response = client.post('/api/refresh', json={'data': [12], 'session_hash': 'history-cpu-test'})
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()['data']
            self.assertEqual(len(data[0]), 1)
            response = client.post('/api/select', json={'data': [None], 'session_hash': 'history-cpu-test',
                                                       'event_data': {'index': 0, 'value': None}})
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()['data']
            # output 0 là State (None bên transport); image/file là filepath cache của Gradio.
            self.assertTrue(data[1]['path'].endswith('.png'))
            self.assertTrue(data[2]['path'].endswith('.png'))
            image_file = Path(data[2]['path'])
            self.assertEqual(image_file.read_bytes(), self.original_bytes)
            downloaded = client.get('/file=' + str(image_file))
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(hashlib.sha256(downloaded.content).hexdigest(), hashlib.sha256(self.original_bytes).hexdigest())
            seed = client.post('/api/use_seed', json={'data': [None], 'session_hash': 'history-cpu-test'})
            self.assertEqual(seed.status_code, 200)
            self.assertEqual(seed.json()['data'][0], 42)
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


    def test_07_selection_signature_rejects_seed_after_file_replaced(self):
        ids = self.panel.refresh()[2]
        token = self.panel.select(ids, gr.SelectData(None, {"index": 0, "value": None}))[0]
        info = PngImagePlugin.PngInfo()
        info.add_text("parameters", "Steps: 25, Seed: 91, Size: 16x16")
        with Image.new("RGB", (16, 16), "black") as image:
            image.save(self.path, pnginfo=info)
        self.store.refresh()
        self.assertEqual(self.panel.use_seed(token)[0], gr.skip())
        fresh = self.panel.select(self.panel.first_page()[2], gr.SelectData(None, {"index": 0, "value": None}))[0]
        self.assertEqual(self.panel.use_seed(fresh)[0], 91)


    def test_08_storage_errors_do_not_break_paging_or_seed_or_dump_data(self):
        with patch.object(self.store, "page", side_effect=sqlite3.DatabaseError("PRIVATE-DATA")):
            for values in (self.panel.first_page(), self.panel.next(1), self.panel.previous(2)):
                self.assertEqual(len(values), 9)
                self.assertNotIn("PRIVATE", repr(values))
        with patch.object(self.store, "get", side_effect=OSError("PRIVATE-PATH")):
            result = self.panel.select([1], gr.SelectData(None, {"index": 0, "value": None}))
            self.assertIsNone(result[0])
            self.assertNotIn("PRIVATE", repr(result))
            self.assertEqual(self.panel.use_seed({"id": 1})[0], gr.skip())


if __name__ == '__main__':
    unittest.main(verbosity=2)
