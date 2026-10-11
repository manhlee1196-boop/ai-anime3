"""Headless Colab: Matplotlib inline lỗi → Agg import/Gradio callback đạt, CPU.

.venv/bin/python colab/tests/test_headless_backend.py
FASTAPI_PROBE_PATH=tools/work/fastapi127-probe để dùng matrix giống runtime người dùng.
Không import Forge/Torch/GPU, không tải weights hay gọi API sinh ảnh.
"""
import ast
import importlib.metadata
import json
import os
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))


class HeadlessBackend(unittest.TestCase):
    def run_python(self, backend, code):
        env = {**os.environ, "MPLBACKEND": backend, "GRADIO_ANALYTICS_ENABLED": "False"}
        if path := os.environ.get("FASTAPI_PROBE_PATH"):
            env["PYTHONPATH"] = str(Path(path).resolve())
        return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=30)

    def test_01_reproduces_inherited_inline_error_on_matplotlib_311(self):
        if not importlib.metadata.version("matplotlib").startswith("3.11"):
            self.skipTest("Reproduction cụ thể dùng Matplotlib 3.11.x như dòng stack runtime")
        result = self.run_python("module://matplotlib_inline.backend_inline", "import matplotlib")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ValueError: Key backend:", result.stderr)
        self.assertIn("not a valid value for backend", result.stderr)
        self.assertIn("__setitem__", result.stderr)

    def test_02_agg_import_styler_and_real_gradio_dataframe(self):
        result = self.run_python("Agg", '''
import json, matplotlib, pandas as pd, gradio as gr
from pandas.io.formats.style import Styler
with gr.Blocks(analytics_enabled=False):
    table = gr.Dataframe(value=pd.DataFrame({'en': ['1girl'], 'vi': ['một cô gái']}), type='pandas')
assert table.value['data'][0] == ['1girl', 'một cô gái']
print(json.dumps({'backend': matplotlib.get_backend(), 'gradio': gr.__version__}))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["backend"].lower(), "agg")

    def test_03_real_settings_load_callback_http_200(self):
        # AST get_value_for_setting của Neo nếu có; fallback tương đương để test offline.
        source = ROOT / "tools/work/current_modules_ui_settings.py"
        function = "def get_value_for_setting(key):\n    return gr.update(value=getattr(opts, key))\n"
        if source.exists():
            node = next(n for n in ast.parse(source.read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == "get_value_for_setting")
            function = ast.get_source_segment(source.read_text(), node)
        code = '''
import json, types, gradio as gr, fastapi, starlette
from fastapi.testclient import TestClient
from gradio.routes import App
opts = types.SimpleNamespace(outdir_txt2img_samples='output/txt2img-images',
                             outdir_img2img_samples='output/img2img-images',
                             data_labels={k: types.SimpleNamespace(component_args={}) for k in ('outdir_txt2img_samples', 'outdir_img2img_samples')})
'''+function+'''
keys = ['outdir_txt2img_samples', 'outdir_img2img_samples']
with gr.Blocks(analytics_enabled=False) as demo:
    first = gr.Textbox(value='')
    second = gr.Textbox(value='')
    demo.load(fn=lambda: [get_value_for_setting(k) for k in keys], inputs=[],
              outputs=[first, second], queue=False, api_name='settings_probe')
with TestClient(App.create_app(demo), raise_server_exceptions=False) as client:
    assert client.get('/info?all_endpoints=True').status_code == 200
    response = client.post('/api/settings_probe', json={'data': [], 'session_hash': 'wai-cpu-test', 'fn_index': 0})
    assert response.status_code == 200, response.text
    assert response.json()['data'][0]['value'] == 'output/txt2img-images'
    assert response.json()['data'][1]['value'] == 'output/img2img-images'
print(json.dumps({'callback_http': response.status_code, 'fastapi': fastapi.__version__, 'starlette': starlette.__version__, 'gradio': gr.__version__}))
'''
        result = self.run_python("Agg", code)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["callback_http"], 200)
        if os.environ.get("FASTAPI_PROBE_PATH"):
            self.assertEqual(data["fastapi"], "0.127.1")
            self.assertEqual(data["starlette"], "0.50.0")

    def test_04_installer_probe_uses_agg_without_changing_parent(self):
        with tempfile.TemporaryDirectory(prefix="wai-headless-installer-") as tmp:
            forge = Path(tmp) / "forge"
            python = forge / "venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/usr/bin/env bash\nexec " + shlex.quote(sys.executable) + " \"$@\"\n")
            python.chmod(0o755)
            env = {**os.environ, "FORGE_DIR": str(forge), "MPLBACKEND": "module://matplotlib_inline.backend_inline"}
            result = subprocess.run(["bash", "-c", 'source "$1"; headless_ui_ready; [[ "$MPLBACKEND" == module://matplotlib_inline.backend_inline ]]',
                                     "test", str(ROOT / "colab/install.sh")],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("headless khởi tạo được", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
