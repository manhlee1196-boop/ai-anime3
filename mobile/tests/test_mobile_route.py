#!/usr/bin/env python3
"""Hồi quy job API + static app; không cần GPU/Gradio/S3 thật.

    python3 mobile/tests/test_mobile_route.py

S3 được kiểm bằng client giả lập (upload/presign); không giả định đã kiểm bucket thật.
"""

import base64
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXT_PATH = ROOT / "colab/extension/vi-prompt-builder/scripts/vi_prompt_tab.py"
JOBS_PATH = EXT_PATH.with_name("mobile_jobs.py")

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except Exception:                                     # noqa: BLE001
    HAVE_FASTAPI = False

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:                                     # noqa: BLE001
    HAVE_PIL = False

GR_NAMES = ("Accordion Button Checkbox CheckboxGroup Dataframe Dropdown Markdown Row Slider "
            "State Tab Tabs Textbox SelectData Blocks Column Gallery Number").split()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_fakes():
    class FakeScript:
        alwayson = False
        create_group = True
        section = None
        sorting_priority = 0

    fake_scripts = types.ModuleType("modules.scripts")
    fake_scripts.Script = FakeScript
    fake_scripts.AlwaysVisible = object()
    modules = types.ModuleType("modules")
    modules.scripts = fake_scripts
    sys.modules["modules"] = modules
    sys.modules["modules.scripts"] = fake_scripts

    gradio = types.ModuleType("gradio")
    gradio.__version__ = "4.40.0"
    for name in GR_NAMES:
        setattr(gradio, name, type(name, (), {}))
    gradio.update = lambda **kwargs: kwargs
    sys.modules["gradio"] = gradio


class FakeRequest:
    def __init__(self, payload):
        if not str(payload.get("prompt") or "").strip() and not payload.get("image"):
            raise ValueError("prompt/image là bắt buộc")
        self.payload = dict(payload)
        for key, value in payload.items():
            setattr(self, key, value)
        self.prompt = payload.get("prompt", "")
        self.negative_prompt = payload.get("negative_prompt", "")
        self.seed = payload.get("seed", -1)
        self.width = payload.get("width", 64)
        self.height = payload.get("height", 64)
        self.batch_size = payload.get("batch_size", 1)
        self.n_iter = payload.get("n_iter", 1)
        self.send_images = True
        self.save_images = False

    def model_dump(self):
        return {**self.payload, "send_images": self.send_images, "save_images": self.save_images}


if HAVE_FASTAPI:
    def require_key(x_api_key: str = Header(default=None)):
        if x_api_key != "secret":
            raise HTTPException(status_code=401, detail="missing key")


@unittest.skipUnless(HAVE_FASTAPI and HAVE_PIL, "cần fastapi + Pillow")
class MobileRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fakes()
        sys.path.insert(0, str(ROOT / "colab"))
        cls.ext = load_module("vi_prompt_tab_route", EXT_PATH)
        cls.jobs = load_module("anime3_mobile_jobs_test", JOBS_PATH)
        cls.real_txt2img_request = cls.ext._txt2img_request
        cls.real_extras_request = cls.ext._extras_request
        cls.real_img2img_request = cls.ext._img2img_request
        cls.ext._txt2img_request = lambda endpoint, payload: FakeRequest(payload)
        cls.ext._extras_request = lambda endpoint, payload: FakeRequest(payload)
        cls.ext._img2img_request = lambda endpoint, payload: FakeRequest(payload)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["ANIME3_MOBILE_JOB_DIR"] = self.temp.name
        self.calls = []
        self.extra_calls = []
        self.img_calls = []
        self.interrupts = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.block_generation = False

        def standard_endpoint(payload: dict):
            self.calls.append(payload.model_dump())
            if self.block_generation:
                self.started.set()
                self.release.wait(5)
            image = Image.new("RGB", (64, 64), (30, 120, 210))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            info = {"seed": 42, "prompt": getattr(payload, "prompt", ""),
                    "width": 64, "height": 64}
            return types.SimpleNamespace(images=[encoded], info=json.dumps(info), parameters={})

        def extras_endpoint(payload: dict):
            self.extra_calls.append(payload.model_dump())
            image = Image.new("RGB", (128, 128), (210, 120, 30))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            # Đúng ExtrasSingleImageResponse của Forge: image số ít + html_info.
            return types.SimpleNamespace(image=encoded, html_info="upscaled")

        def img2img_endpoint(payload: dict):
            self.img_calls.append(payload.model_dump())
            image = Image.new("RGB", (64, 64), (90, 180, 80))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            info = {"seed": 43, "prompt": getattr(payload, "prompt", ""),
                    "width": 64, "height": 64}
            return types.SimpleNamespace(images=[encoded], info=json.dumps(info), parameters={})

        def interrupt():
            self.interrupts += 1

        self.app = FastAPI()
        dependencies = [Depends(require_key)] if self._testMethodName == "test_09_auth_dependencies" else []
        self.app.add_api_route("/sdapi/v1/txt2img", standard_endpoint,
                               methods=["POST"], dependencies=dependencies)
        self.app.add_api_route("/sdapi/v1/extra-single-image", extras_endpoint,
                               methods=["POST"], dependencies=dependencies)
        self.app.add_api_route("/sdapi/v1/img2img", img2img_endpoint,
                               methods=["POST"], dependencies=dependencies)
        self.app.add_api_route("/sdapi/v1/interrupt", interrupt, methods=["POST"])
        self.manager = self.ext.serve_mobile_app(None, self.app)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.release.set()
        self.client.__exit__(None, None, None)
        self.temp.cleanup()
        os.environ.pop("ANIME3_MOBILE_JOB_DIR", None)

    def auth_headers(self):
        return {"x-api-key": "secret"} if self._testMethodName == "test_09_auth_dependencies" else {}

    def create_job(self, key="request-1", payload=None):
        return self.client.post("/vi-mobile/api/jobs", headers=self.auth_headers(), json={
            "payload": payload or {"prompt": "1girl", "seed": 42, "width": 64, "height": 64},
            "idempotency_key": key,
        })

    def wait_job(self, job_id, final=("done", "error", "cancelled")):
        deadline = time.time() + 6
        while time.time() < deadline:
            response = self.client.get(f"/vi-mobile/api/jobs/{job_id}", headers=self.auth_headers())
            self.assertEqual(response.status_code, 200, response.text)
            job = response.json()
            if job["status"] in final:
                return job
            time.sleep(0.02)
        self.fail("job không đạt trạng thái cuối")

    def test_01_static_app_and_health(self):
        self.assertEqual(Path(self.ext.mobile_app_dir()), ROOT / "mobile" / "app")
        self.assertFalse(hasattr(self.ext, "on_ui_tabs"))
        redirect = self.client.get("/vi-mobile", follow_redirects=False)
        self.assertEqual(redirect.status_code, 307)
        index = self.client.get("/vi-mobile/")
        self.assertEqual(index.status_code, 200)
        self.assertIn('id="generateBtn"', index.text)
        for path in ("styles.css", "js/core.js", "js/ui.js", "manifest.webmanifest",
                     "icons/icon-192.png", "sw.js", "data/tags.json.gz"):
            self.assertEqual(self.client.get(f"/vi-mobile/{path}").status_code, 200, path)
        health = self.client.get("/vi-mobile/api/health", headers=self.auth_headers())
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["async_jobs"])
        self.assertTrue(health.json()["extras_available"])
        self.assertTrue(health.json()["img2img_available"])
        self.assertIn("object_storage", health.json())

    def test_02_job_idempotency_original_png_manifest_and_range(self):
        created = self.create_job()
        self.assertEqual(created.status_code, 202, created.text)
        job_id = created.json()["job_id"]
        duplicate = self.create_job()
        self.assertEqual(duplicate.status_code, 202)
        self.assertEqual(duplicate.json()["job_id"], job_id)
        self.assertTrue(duplicate.json()["deduplicated"])
        self.assertEqual(self.wait_job(job_id)["status"], "done")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.calls[0]["send_images"])
        self.assertFalse(self.calls[0]["save_images"])

        manifest_response = self.client.get(f"/vi-mobile/api/jobs/{job_id}/result",
                                            headers=self.auth_headers())
        self.assertEqual(manifest_response.status_code, 200)
        manifest = manifest_response.json()
        self.assertEqual(manifest["info"]["seed"], 42)
        self.assertNotIn("base64", manifest_response.text)
        self.assertEqual(len(manifest["files"]), 1)
        item = manifest["files"][0]
        self.assertEqual(item["storage"], "local")
        self.assertEqual(item["mime"], "image/png")
        self.assertTrue(item["name"].endswith(".png"))

        full = self.client.get(item["url"], headers=self.auth_headers())
        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.content[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(int(full.headers["content-length"]), item["size"])
        part = self.client.get(item["url"], headers={**self.auth_headers(), "Range": "bytes=10-"})
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, full.content[10:])
        self.assertEqual(part.headers["content-range"], f"bytes 10-{len(full.content)-1}/{len(full.content)}")
        invalid = self.client.get(item["url"], headers={**self.auth_headers(), "Range": "bytes=0-1,4-5"})
        self.assertEqual(invalid.status_code, 416)

    def test_03_invalid_payload_is_422_and_never_reaches_gpu(self):
        response = self.create_job(payload={"width": 64})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])

    def test_04_cancel_running_interrupts_and_never_publishes_result(self):
        self.block_generation = True
        self.release.clear()
        job_id = self.create_job().json()["job_id"]
        self.assertTrue(self.started.wait(2))
        self.assertEqual(self.client.get(f"/vi-mobile/api/jobs/{job_id}/result").status_code, 409)
        cancelled = self.client.delete(f"/vi-mobile/api/jobs/{job_id}")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertEqual(self.interrupts, 1)
        self.release.set()
        self.assertEqual(self.wait_job(job_id)["status"], "cancelled")
        self.assertEqual(self.client.get(f"/vi-mobile/api/jobs/{job_id}/result").status_code, 409)
        self.assertEqual(self.client.get(f"/vi-mobile/api/files/{job_id}/000.png").status_code, 404)

    def test_05_cancel_queued_job_does_not_run_it(self):
        self.block_generation = True
        self.release.clear()
        first = self.create_job("first").json()["job_id"]
        self.assertTrue(self.started.wait(2))
        second = self.create_job("second", {"prompt": "không được chạy", "width": 64, "height": 64}).json()["job_id"]
        self.assertEqual(self.client.get("/vi-mobile/api/health").json()["active_jobs"], 2)
        self.assertEqual(self.client.delete(f"/vi-mobile/api/jobs/{second}").json()["status"], "cancelled")
        self.release.set()
        self.assertEqual(self.wait_job(first)["status"], "done")
        self.assertEqual(self.wait_job(second)["status"], "cancelled")
        self.assertEqual(len(self.calls), 1)
        self.assertNotEqual(self.calls[0].get("prompt"), "không được chạy")

    def test_06_s3_upload_and_signed_url_with_mock_client(self):
        class FakeS3Client:
            def __init__(self):
                self.uploads = []
                self.expiry = None

            def upload_file(self, path, bucket, key, ExtraArgs):
                self.uploads.append((path, bucket, key, ExtraArgs))

            def generate_presigned_url(self, operation, Params, ExpiresIn):
                self.expiry = ExpiresIn
                return f"https://signed.example/{Params['Key']}?signature=mock"

        fake = FakeS3Client()
        storage = self.jobs.S3Storage({
            "ANIME3_S3_BUCKET": "bucket",
            "ANIME3_S3_ENDPOINT_URL": "https://r2.example",
            "ANIME3_S3_REGION": "auto",
            "ANIME3_S3_ACCESS_KEY_ID": "key",
            "ANIME3_S3_SECRET_ACCESS_KEY": "secret",
            "ANIME3_S3_PREFIX": "anime3",
            "ANIME3_S3_SIGNED_TTL": "300",
        })
        storage._client = lambda: fake
        self.manager.storage = storage
        job_id = self.create_job().json()["job_id"]
        self.assertEqual(self.wait_job(job_id)["status"], "done")
        manifest = self.client.get(f"/vi-mobile/api/jobs/{job_id}/result").json()
        item = manifest["files"][0]
        self.assertEqual(item["storage"], "s3")
        self.assertTrue(item["url"].startswith("https://signed.example/anime3/"))
        self.assertIn("signature=mock", item["url"])
        self.assertEqual(fake.expiry, 300)
        self.assertEqual(fake.uploads[0][1:3], ("bucket", f"anime3/{job_id}/000.png"))
        self.assertEqual(fake.uploads[0][3]["ContentType"], "image/png")

    def test_07_s3_failure_falls_back_to_local_without_new_job(self):
        class BrokenStorage:
            configured = True
            prefix = "anime3"

            def upload(self, path, key, mime):
                raise RuntimeError("R2 unavailable")

        self.manager.storage = BrokenStorage()
        job_id = self.create_job().json()["job_id"]
        self.assertEqual(self.wait_job(job_id)["status"], "done")
        self.assertEqual(len(self.calls), 1)
        manifest = self.client.get(f"/vi-mobile/api/jobs/{job_id}/result").json()
        self.assertIn("RuntimeError", manifest["storage_warning"])
        self.assertEqual(manifest["files"][0]["storage"], "local")
        self.assertEqual(self.client.get(manifest["files"][0]["url"]).status_code, 200)

    def test_08_restart_marks_queued_job_interrupted_without_rerunning(self):
        job_id = "f" * 32
        record = {
            "job_id": job_id, "status": "queued", "created_at": time.time(),
            "updated_at": time.time(), "payload": {"prompt": "1girl"},
            "idempotency_hash": "interrupted", "info": {}, "error": "", "files": [],
            "storage_warning": "",
        }
        self.manager._save(record)
        restarted = self.jobs.MobileJobManager(
            root=self.temp.name, endpoint_provider=lambda: None,
            request_factory=self.ext._txt2img_request, result_dict=self.ext._result_dict,
            interrupt_provider=lambda: None,
        )
        recovered = restarted.get(job_id)
        self.assertEqual(recovered["status"], "error")
        self.assertIn("khởi động lại", recovered["error"])
        self.assertEqual(restarted.jobs[job_id]["files"], [])

    def test_09_auth_dependencies(self):
        self.assertEqual(self.client.get("/vi-mobile/api/health").status_code, 401)
        self.assertEqual(self.client.post("/vi-mobile/api/jobs", json={
            "payload": {"prompt": "1girl"}, "idempotency_key": "no-auth",
        }).status_code, 401)
        self.assertEqual(self.calls, [])
        created = self.create_job()
        self.assertEqual(created.status_code, 202)
        job_id = created.json()["job_id"]
        self.assertEqual(self.client.get(f"/vi-mobile/api/jobs/{job_id}").status_code, 401)
        self.assertEqual(self.wait_job(job_id)["status"], "done")
        item = self.client.get(f"/vi-mobile/api/jobs/{job_id}/result",
                               headers=self.auth_headers()).json()["files"][0]
        self.assertEqual(self.client.get(item["url"]).status_code, 401)
        self.assertEqual(self.client.get(item["url"], headers=self.auth_headers()).status_code, 200)

    def test_10_hires_defaults_to_same_vae_and_text_encoders(self):
        """Không để None đi vào modules_change() của Forge Neo ở pass Hires."""
        captured = []

        class FakeModel:
            @classmethod
            def model_validate(cls, payload):
                captured.append(payload)
                return payload

        def endpoint(txt2imgreq: FakeModel):
            return txt2imgreq

        source = {"prompt": "1girl", "enable_hr": True}
        request = type(self).real_txt2img_request(endpoint, source)
        self.assertEqual(request["hr_additional_modules"], ["Use same choices"])
        self.assertNotIn("hr_additional_modules", source, "không được sửa payload đầu vào")

        explicit = type(self).real_txt2img_request(endpoint, {
            "prompt": "1girl", "enable_hr": True, "hr_additional_modules": [],
        })
        self.assertEqual(explicit["hr_additional_modules"], [], "giữ lựa chọn Built-in của client")

        disabled = type(self).real_txt2img_request(endpoint, {"prompt": "1girl", "enable_hr": False})
        self.assertNotIn("hr_additional_modules", disabled)
        self.assertEqual(len(captured), 3)

    def test_11_extras_upscale_uses_background_job_and_binary_manifest(self):
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        response = self.client.post("/vi-mobile/api/jobs", json={
            "operation": "extras",
            "payload": {"image": encoded, "resize_mode": 0, "upscaling_resize": 2,
                        "upscaler_1": "RealESRGAN_x4plus_anime_6B", "upscaler_2": "None"},
            "idempotency_key": "upscale-one",
        })
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        self.assertEqual(self.wait_job(job_id)["status"], "done")
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.extra_calls), 1)
        self.assertEqual(self.extra_calls[0]["upscaling_resize"], 2)
        self.assertEqual(self.manager.jobs[job_id]["payload"], {})
        manifest = self.client.get(f"/vi-mobile/api/jobs/{job_id}/result").json()
        self.assertEqual(manifest["info"], {"raw": "upscaled"})
        image = self.client.get(manifest["files"][0]["url"])
        self.assertEqual(image.status_code, 200)
        with Image.open(io.BytesIO(image.content)) as output:
            self.assertEqual(output.size, (128, 128))
        invalid = self.client.post("/vi-mobile/api/jobs", json={
            "operation": "extras", "payload": {"image": "không-phải-base64"},
        })
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(len(self.extra_calls), 1)
        oversized_buffer = io.BytesIO()
        Image.new("L", (4097, 1), 255).save(oversized_buffer, format="PNG")
        oversized = self.client.post("/vi-mobile/api/jobs", json={
            "operation": "extras",
            "payload": {"image": base64.b64encode(oversized_buffer.getvalue()).decode("ascii"),
                        "resize_mode": 0, "upscaling_resize": 1,
                        "upscaler_1": "Lanczos"},
        })
        self.assertEqual(oversized.status_code, 422)
        self.assertEqual(len(self.extra_calls), 1, "ảnh quá lớn không được đưa vào GPU")

    def test_12_img2img_uses_init_image_and_binary_background_job(self):
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "navy").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        body = {
            "operation": "img2img",
            "payload": {"prompt": "1girl, long_hair", "init_images": [encoded],
                        "denoising_strength": 0.55, "resize_mode": 1,
                        "width": 64, "height": 64, "steps": 25},
            "idempotency_key": "img2img-one",
        }
        response = self.client.post("/vi-mobile/api/jobs", json=body)
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        self.assertEqual(self.wait_job(job_id)["status"], "done")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.extra_calls, [])
        self.assertEqual(len(self.img_calls), 1)
        self.assertEqual(self.img_calls[0]["init_images"], [encoded])
        self.assertEqual(self.img_calls[0]["denoising_strength"], 0.55)
        self.assertTrue(self.img_calls[0]["send_images"])
        duplicate = self.client.post("/vi-mobile/api/jobs", json=body)
        self.assertEqual(duplicate.json()["job_id"], job_id)
        self.assertEqual(len(self.img_calls), 1)
        manifest = self.client.get(f"/vi-mobile/api/jobs/{job_id}/result").json()
        image = self.client.get(manifest["files"][0]["url"])
        self.assertEqual(image.status_code, 200)
        self.assertTrue(image.content.startswith(b"\x89PNG"))
        invalid = self.client.post("/vi-mobile/api/jobs", json={
            "operation": "img2img", "payload": {"prompt": "1girl", "init_images": []},
        })
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(len(self.img_calls), 1)

        captured = []

        class FakeImg2ImgModel:
            @classmethod
            def model_validate(cls, value):
                captured.append(value)
                return value

        api_module = types.ModuleType("modules.api")
        api_module.models = types.SimpleNamespace(
            StableDiffusionImg2ImgProcessingAPI=FakeImg2ImgModel)
        previous_api = sys.modules.get("modules.api")
        sys.modules["modules.api"] = api_module
        try:
            def delayed_endpoint(img2imgreq: "StableDiffusionImg2ImgProcessingAPI"):
                return img2imgreq

            source = dict(body["payload"])
            type(self).real_img2img_request(delayed_endpoint, source)
        finally:
            if previous_api is None:
                sys.modules.pop("modules.api", None)
            else:
                sys.modules["modules.api"] = previous_api
        self.assertEqual(captured, [source])
        self.assertEqual(captured[0]["denoising_strength"], 0.55)


if __name__ == "__main__":
    unittest.main(verbosity=2)
