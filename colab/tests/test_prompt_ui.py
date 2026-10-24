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
    app.STYLES = app.StyleLibrary(ROOT)
    app_ui = app.build_ui()
    # mục chọn phong cách: có dropdown nhóm + checkbox group + nút thêm
    components = app_ui.get_config_file()["components"]
    labels = [c["props"].get("label", "") for c in components]
    assert "Nhóm phong cách" in labels and "Công thức sẵn (chọn là tick sẵn)" in labels
    assert any("Tick tag phong cách" in label for label in labels)
    # mở app là thấy đủ 506 tag trong danh sách tick (nhóm mặc định "Tất cả")
    tick = next(c["props"] for c in components
                if c["props"].get("label", "").startswith("Tick tag phong cách"))
    assert len(tick["choices"]) == 506 and tick["visible"] is not False
    all_label = app.STYLES.all_label()
    assert app.STYLES.is_all(all_label) and len(app.STYLES.choices()) == 506
    group_box = next(c["props"] for c in components
                     if c["props"].get("label") == "Nhóm phong cách")
    assert group_box["value"] == all_label and len(group_box["choices"]) == 10
    checked, rows, note, showcase = app.do_style_group(all_label, "")
    assert len(checked["choices"]) == 506 and checked["visible"] is True
    assert len(rows) == 506 and "Tất cả" in note and showcase["visible"] is True
    # lọc theo nhóm: vẫn hiện, không ẩn; tag đang tick được giữ nếu còn trong phạm vi
    light = app.STYLES.choices("Ánh sáng")
    checked, rows, note, _ = app.do_style_group("Ánh sáng", "", [light[0]])
    assert len(checked["choices"]) == len(light) and checked["visible"] is True
    assert checked["value"] == [light[0]] and "ánh sáng" in note.lower()
    checked, rows, note, showcase = app.do_style_group(all_label, "màu nước")
    assert 0 < len(checked["choices"]) < 20 and showcase["visible"] is False
    assert [app.STYLES.tag_of(c) for c in checked["choices"]][:1] == ["watercolor_(medium)"]
    # công thức: 4 tag tick sẵn ở đầu nhưng các tag khác vẫn còn trong danh sách
    checked, rows, note = app.do_style_preset("Pixel art game cũ", all_label)
    assert len(checked["value"]) == 4 and "pixel_art" in checked["choices"][0]
    assert len(checked["choices"]) == 506 and checked["visible"] is True
    assert checked["choices"][:4] == checked["value"] and len(rows) == 4
    # prompt dài: có mục đo/nén, và cảnh báo độ dài nằm ngay dưới ô positive
    assert any("Prompt dài" in label for label in labels)
    long_prompt = app.do_build("1girl, blue_eyes, eyes, long_hair, smile", "", app.RATING_CHOICES[0],
                               "Ngắn gọn", "WAI khuyến nghị (ngắn)", "", "", "", False)[4]
    assert "token" in long_prompt and "cửa sổ" in long_prompt
    length_note, window_rows = app.do_length("1girl, blue_eyes, long_hair")
    assert "cửa sổ" in length_note and len(window_rows) == 1
    compacted, compact_note, compact_rows = app.do_compact("1girl, blue_eyes, eyes, long_hair")
    assert "eyes" not in [p.strip() for p in compacted.split(",")]
    assert "blue_eyes" in compacted and "Đã bỏ" in compact_note
    assert app.do_length("")[1] == [] and app.do_compact("")[0] == ""

    merged, queued = app.do_style_add("1girl", checked["value"])
    assert merged.startswith("1girl") and all(t in merged for t in
                                              ("pixel_art", "pixel_animation", "limited_palette"))
    assert app.do_style_add("1girl", [])[0] == "1girl"
    slider = cfg_slider(app_ui)
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
    extension_ui = extension.build_tab()
    slider = cfg_slider(extension_ui)
    assert slider["value"] == 1.0 and slider["minimum"] <= 1.0
    built = extension.do_build("1girl, ao_dai, long_hair", "", extension.RATING_CHOICES[0],
                               "WAI khuyến nghị (đầy đủ)", "Chuẩn cộng đồng (đầy đủ)", "", "", "")
    assert isinstance(built[2], list) and all(isinstance(row, list) and len(row) == 2 for row in built[2])
    for module, ui in ((app, app_ui), (extension, extension_ui)):
        # cả app và tab Forge đều hiện đủ tag, không ẩn danh sách
        full, _rows, _note, _show = module.do_style_group(module.STYLES.all_label(), "")
        assert len(full["choices"]) == 506 and full["visible"] is True
        preset, _prows, _pnote = module.do_style_preset("Tranh màu nước",
                                                        module.STYLES.all_label())
        assert len(preset["choices"]) == 506 and len(preset["value"]) == 4
        assert preset["choices"][:4] == preset["value"]
        assert module._merge("1girl, (áo dài:1.2), long_hair", ["ao_dai"]) == "1girl, (ao_dai:1.2), long_hair"
        assert module.do_convert("1girl, áo dài, tóc dài")[0] == "1girl, ao_dai, long_hair"
        components = ui.get_config_file()["components"]
        assert any(c["props"].get("label") == "Quy trình" for c in components)
        assert any(c["props"].get("label", "").startswith("Bảng ảnh đã tạo") for c in components)
        assert ui.wai_history_panel.ids.value == []
        assert any(dep.get("trigger_only_on_success") for dep in ui.get_config_file()["dependencies"])
        assert all(not c["props"].get("value") for c in components
                   if c["type"] == "checkbox" and c["props"].get("label", "").startswith("Hires"))
        assert len(module.set_workflow("Hoàn thiện — Hires 1.5×")) == 9
        assert module.set_workflow("Hoàn thiện — Hires 1.5×", "DPM++ 2M Karras")[2] == "DPM++ 2M Karras"
        assert module.set_workflow("Hoàn thiện — Hires 1.5×")[-1] == 1
        assert module.do_convert("1girl, 1girl, áo dài, ao_dai, (tóc dài:1.2)")[0] == "1girl, 1girl, ao_dai, (long_hair:1.2)"
        assert module.set_workflow("Hoàn thiện — Hires 1.5×")[0:2] == (10, 1.0)
    print("✔ Tab/app: đổi Việt tại chỗ, workflow/HSWQ, Hires mặc định tắt")

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
        images, note, meta = extension.do_generate(built[0], built[1], "Vuông 1024×1024",
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
        images, note, meta = app.do_generate("masterpiece, landscape", "lowres", "Vuông 1024×1024",
                                      10, 1.0, "DPM++ 2M Karras", 1, 1, True, 1.5, 10, 0.4,
                                      "RealESRGAN_x4plus_anime_6B", "http://127.0.0.1:7860")
        assert len(images) == 1 and isinstance(images[0], Image.Image)
        assert "seed `1`" in note
        assert captured[-1]["sampler_name"] == "DPM++ 2M" and captured[-1]["scheduler"] == "Karras"
        assert captured[-1]["override_settings"]["clip_stop_at_last_layers"] == 2
        assert "clip_skip" not in captured[-1]
        assert app.use_image_seed(meta, 0)[0] == 1
        count = len(captured)
        images, note, _ = app.do_generate("landscape", "", "Vuông 1024×1024", 0, float("nan"), "Euler a", 1, 1,
                                         False, 1.5, 10, 0.4, "None", "http://127.0.0.1:7860")
        assert images == [] and "không hợp lệ" in note and len(captured) == count
        images, note, _ = app.do_generate("landscape", "", "Vuông 1024×1024", 10, 1, "Euler a", 1, 3,
                                         False, 1.5, 10, 0.4, "None", "http://127.0.0.1:7860")
        assert captured[-1]["batch_size"] == 1 and captured[-1]["n_iter"] == 3
        assert captured[-1]["save_images"] is True
        api_options["sd_model_checkpoint"] = None
        connected, note = app.forge_alive()
        assert not connected and "chưa chọn Checkpoint" in note
        api_options["sd_model_checkpoint"] = "fixture.safetensors"
        app.requests.post = lambda *args, **kwargs: Response({"images": [], "info": "{}"})
        images, note, meta = app.do_generate("landscape", "", "Vuông 1024×1024", 10, 1.0, "Euler a", 1, 1,
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
