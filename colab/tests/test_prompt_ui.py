"""Smoke test app/tab Gradio với profile HSWQ; không chạy Forge/GPU thật.

Cần gradio, requests, pillow. Chạy trong venv của Forge hoặc venv demo:
  python colab/tests/test_prompt_ui.py

Mô phỏng duy nhất modules/script_callbacks của Forge và response API PNG + info
JSON-string. UI thực sự được dựng, slider phải chứa CFG=1, gallery phải nhận PIL.
"""
import base64
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
os.environ["WAI_PROFILE_MODEL_ID"] = "hswq"
os.environ["VI_PROMPT_ROOT"] = str(ROOT)

import gradio as gr  # noqa: E402
from PIL import Image  # noqa: E402
import prompt_builder as app  # noqa: E402
from prompt_lib.system_tags import apply_model_profile, profile_environment  # noqa: E402


def cfg_slider(ui):
    return next(c["props"] for c in ui.get_config_file()["components"]
                if c["type"] == "slider" and c["props"].get("label", "").startswith("CFG"))


def main():
    app.INDEX = app.TagIndex(ROOT)
    app.BUILDER = app.PromptBuilder(app.INDEX)
    slider = cfg_slider(app.build_ui())
    assert slider["minimum"] <= 1.0 <= slider["maximum"] and slider["value"] == 1.0
    assert "hswq" in app.profile_note()
    print(f"✔ App Gradio {gr.__version__}: HSWQ CFG=1 / steps=10, UI hợp lệ")

    # Forge host module giả lập: không import tensor engine hoặc khởi chạy server.
    modules = types.ModuleType("modules")
    modules.shared = types.SimpleNamespace(cmd_opts=types.SimpleNamespace(port=7860))
    modules.script_callbacks = types.SimpleNamespace(on_ui_tabs=lambda callback: None)
    sys.modules["modules"] = modules
    path = ROOT / "colab/extension/vi-prompt-builder/scripts/vi_prompt_tab.py"
    spec = importlib.util.spec_from_file_location("vi_prompt_tab_test", path)
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    slider = cfg_slider(extension.build_tab())
    assert slider["value"] == 1.0 and slider["minimum"] <= 1.0
    built = extension.do_build("1girl, ao_dai, long_hair", "", extension.RATING_CHOICES[0],
                               "WAI khuyến nghị (đầy đủ)", "Chuẩn cộng đồng (đầy đủ)", "", "", "")
    assert isinstance(built[2], list) and all(isinstance(row, list) and len(row) == 2 for row in built[2])
    print("✔ Tab Prompt VN: dựng UI và bảng nhóm đúng định dạng Dataframe")

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    png = base64.b64encode(buffer.getvalue()).decode()
    captured = []

    class Response:
        def __init__(self, data):
            self.data = data
            self.status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return self.data

    api_options = {"sd_model_checkpoint": "fixture.safetensors", "forge_preset": "xl", "forge_checkpoint_xl": "fixture.safetensors"}
    def get(url, **kwargs):
        if url.endswith("/options"):
            return Response(api_options)
        return Response([{"name": "RealESRGAN_x4plus_anime_6B"}])
    def post(url, json=None, **kwargs):
        captured.append(json)
        return Response({"images": [png], "info": __import__("json").dumps(
            {"seed": 1, "width": 8, "height": 8, "cfg_scale": 1.0, "steps": 10})})

    old_get, old_post = extension.requests.get, extension.requests.post
    try:
        extension.requests.get, extension.requests.post = get, post
        images, note = extension.do_generate(built[0], built[1], "Vuông 1024×1024",
                                              10, 1.0, "Euler a", 1, True, 1.5, 0.4,
                                              "RealESRGAN_x4plus_anime_6B")
    finally:
        extension.requests.get, extension.requests.post = old_get, old_post
    assert len(images) == 1 and isinstance(images[0], Image.Image)
    assert "seed `1`" in note and "CFG 1.0" in note
    assert captured[0]["hr_second_pass_steps"] == 10
    print("✔ API giả lập: đọc info JSON-string, PNG → PIL, hires steps theo HSWQ")

    # App độc lập cũng phải đi hết đường sinh ảnh, không chỉ dựng được UI.
    try:
        app.requests.get, app.requests.post = get, post
        images, note = app.do_generate("masterpiece, landscape", "lowres", "Vuông 1024×1024",
                                      10, 1.0, "DPM++ 2M Karras", 1, 1, True, 1.5, 10, 0.4,
                                      "RealESRGAN_x4plus_anime_6B", "http://127.0.0.1:7860")
        assert len(images) == 1 and isinstance(images[0], Image.Image)
        assert "seed `1`" in note
        assert captured[-1]["sampler_name"] == "DPM++ 2M" and captured[-1]["scheduler"] == "Karras"
        api_options["sd_model_checkpoint"] = None
        connected, note = app.forge_alive()
        assert not connected and "chưa chọn Checkpoint" in note
        api_options["sd_model_checkpoint"] = "fixture.safetensors"
        app.requests.post = lambda *args, **kwargs: Response({"images": [], "info": "{}"})
        images, note = app.do_generate("landscape", "", "Vuông 1024×1024", 10, 1.0, "Euler a", 1, 1,
                                      False, 1.5, 10, 0.4, "None", "http://127.0.0.1:7860")
        assert images == [] and "không hợp lệ" in note
    finally:
        app.requests.get, app.requests.post = old_get, old_post
    print("✔ App sinh ảnh: JSON-string/PIL, tách sampler/scheduler, báo checkpoint trống và response hỏng")

    # App độc lập đọc profile lưu trên đĩa, nhưng environment vẫn được ưu tiên.
    with tempfile.TemporaryDirectory(prefix="wai-profile-test-") as tmp:
        profile = Path(tmp) / "profile.json"
        profile.write_text(json.dumps({"WAI_PROFILE_MODEL_ID": "fp8"}))
        old_id, old_file = os.environ.pop("WAI_PROFILE_MODEL_ID"), os.environ.get("WAI_PROFILE_FILE")
        try:
            os.environ["WAI_PROFILE_FILE"] = str(profile)
            d = dict(app.WAI_DEFAULTS)
            mid, _ = apply_model_profile(d, profile_environment())
            assert mid == "fp8" and d["cfg_scale"] == 6.5
            os.environ["WAI_PROFILE_MODEL_ID"] = "hswq"
            d = dict(app.WAI_DEFAULTS)
            mid, _ = apply_model_profile(d, profile_environment())
            assert mid == "hswq" and d["cfg_scale"] == 1.0
            for value in ("nan", "inf", "-1", "100"):
                d = {"cfg_scale": 6.0}
                apply_model_profile(d, {"WAI_PROFILE_CFG": value})
                assert d["cfg_scale"] == 6.0
        finally:
            os.environ["WAI_PROFILE_MODEL_ID"] = old_id
            if old_file is None:
                os.environ.pop("WAI_PROFILE_FILE", None)
            else:
                os.environ["WAI_PROFILE_FILE"] = old_file
    print("✔ Profile JSON lưu trên đĩa; env ưu tiên; bỏ qua CFG rác/NaN/ngoài khoảng")
    print("TẤT CẢ SMOKE TEST UI ĐỀU ĐẠT (API/Forge host giả lập, chưa sinh ảnh trên GPU)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
