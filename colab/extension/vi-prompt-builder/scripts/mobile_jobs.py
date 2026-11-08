"""Job txt2img bất đồng bộ + file stream cho app Anime3.

Module không import Forge ở top-level để có thể test bằng FastAPI giả lập. Handler và
request/response adapter của Forge được truyền từ vi_prompt_tab.py. Không có base64 trong
response API và không tự chạy lại job sau restart/lỗi tải file.
"""

import base64
import hashlib
import json
import os
import queue
import re
import threading
import time
import uuid
from pathlib import Path

API_ROOT = "/vi-mobile/api"


def _atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(path)


def _decode_image(encoded):
    """Trả (bytes, extension, MIME), giữ nguyên dữ liệu ảnh gốc từ Forge."""
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Forge trả ảnh rỗng")
    raw = encoded.split(",", 1)[1] if encoded.startswith("data:") else encoded
    data = base64.b64decode(raw, validate=True)
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "jpg", "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, "webp", "image/webp"
    raise ValueError("Định dạng ảnh không được hỗ trợ")


def _public_job(job):
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "error": job.get("error") or "",
        "storage_warning": job.get("storage_warning") or "",
    }


class S3Storage:
    """S3/AWS hoặc R2 tương thích S3; credential chỉ đọc từ environment server."""

    def __init__(self, environ=None):
        env = os.environ if environ is None else environ
        self.bucket = (env.get("ANIME3_S3_BUCKET") or "").strip()
        self.endpoint = (env.get("ANIME3_S3_ENDPOINT_URL") or "").strip()
        self.region = (env.get("ANIME3_S3_REGION") or "auto").strip()
        self.prefix = (env.get("ANIME3_S3_PREFIX") or "anime3").strip("/ ")
        self.ttl = max(300, min(86400, int(env.get("ANIME3_S3_SIGNED_TTL") or 3600)))
        self.access_key = (env.get("ANIME3_S3_ACCESS_KEY_ID") or "").strip()
        self.secret_key = (env.get("ANIME3_S3_SECRET_ACCESS_KEY") or "").strip()

    @property
    def configured(self):
        return bool(self.bucket)

    def _client(self):
        if not self.configured:
            return None
        if not self.access_key or not self.secret_key:
            raise RuntimeError("Thiếu ANIME3_S3_ACCESS_KEY_ID/SECRET_ACCESS_KEY")
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint or None,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def upload(self, path, key, mime):
        self._client().upload_file(
            str(path), self.bucket, key,
            ExtraArgs={"ContentType": mime, "CacheControl": "private, max-age=86400"},
        )

    def signed_url(self, key, mime, download_name):
        return self._client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentType": mime,
                "ResponseContentDisposition": f'inline; filename="{download_name}"',
            },
            ExpiresIn=self.ttl,
        )


class MobileJobManager:
    def __init__(self, root, endpoint_provider, request_factory, result_dict,
                 interrupt_provider=None, storage=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.endpoint_provider = endpoint_provider
        self.request_factory = request_factory
        self.result_dict = result_dict
        self.interrupt_provider = interrupt_provider
        self.storage = storage or S3Storage()
        self.jobs = {}
        self.idempotency = {}
        self.lock = threading.RLock()
        self.waiting = queue.Queue()
        self._load_jobs()
        self.worker = threading.Thread(target=self._work_loop, daemon=True,
                                       name="anime3-mobile-jobs")
        self.worker.start()

    def _path(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id or ""):
            raise ValueError("job_id không hợp lệ")
        return self.root / job_id

    def _load_jobs(self):
        for directory in self.root.iterdir():
            if not directory.is_dir() or not re.fullmatch(r"[a-f0-9]{32}", directory.name):
                continue
            try:
                job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            # Không bao giờ tự chạy lại payload sau restart Forge.
            if job.get("status") in {"queued", "running", "uploading"}:
                job["status"] = "error"
                job["error"] = "Forge đã khởi động lại; job cũ không được tự chạy lại."
                job["updated_at"] = time.time()
                job["payload"] = {}
                _atomic_json(directory / "job.json", job)
            self.jobs[job["job_id"]] = job
            if job.get("idempotency_hash"):
                self.idempotency[job["idempotency_hash"]] = job["job_id"]

    def _save(self, job):
        job["updated_at"] = time.time()
        _atomic_json(self._path(job["job_id"]) / "job.json", job)

    def submit(self, payload, idempotency_key=""):
        key_hash = hashlib.sha256((idempotency_key or "").encode("utf-8")).hexdigest() \
            if idempotency_key else ""
        with self.lock:
            if key_hash and key_hash in self.idempotency:
                job = self.jobs[self.idempotency[key_hash]]
                return dict(_public_job(job), deduplicated=True)
            job_id = uuid.uuid4().hex
            now = time.time()
            job = {
                "job_id": job_id,
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "payload": payload,
                "idempotency_hash": key_hash,
                "info": {},
                "files": [],
                "error": "",
                "storage_warning": "",
            }
            directory = self._path(job_id)
            directory.mkdir(parents=True, exist_ok=False)
            self.jobs[job_id] = job
            if key_hash:
                self.idempotency[key_hash] = job_id
            _atomic_json(directory / "job.json", job)
            self.waiting.put(job_id)
            return dict(_public_job(job), deduplicated=False)

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return _public_job(job) if job else None

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if job["status"] in {"done", "error", "cancelled"}:
                return _public_job(job)
            was_running = job["status"] in {"running", "uploading"}
            job["status"] = "cancelled"
            job["payload"] = {}
            self._save(job)
        if was_running and self.interrupt_provider:
            try:
                interrupt = self.interrupt_provider()
                if interrupt:
                    interrupt()
            except Exception:
                pass  # trạng thái cancel vẫn được giữ; không đưa job vào lại queue
        return _public_job(job)

    def result(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if job["status"] != "done":
                raise RuntimeError(f"Job chưa hoàn tất: {job['status']}")
            files = []
            for item in job["files"]:
                entry = {key: item[key] for key in ("name", "size", "mime")}
                if item.get("storage") == "s3":
                    entry.update(url=self.storage.signed_url(item["key"], item["mime"], item["name"]),
                                 storage="s3", expires_in=self.storage.ttl)
                else:
                    entry.update(url=f"{API_ROOT}/files/{job_id}/{item['name']}", storage="local")
                files.append(entry)
            return {
                "job_id": job_id,
                "info": job.get("info") or {},
                "files": files,
                "storage_warning": job.get("storage_warning") or "",
            }

    def file_path(self, job_id, name):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None, ""
            item = next((entry for entry in job["files"] if entry["name"] == name), None)
            if not item or item.get("storage") == "s3":
                return None, ""
            path = self._path(job_id) / name
            return (path, item["mime"]) if path.is_file() else (None, "")

    def _set_status(self, job_id, status):
        with self.lock:
            job = self.jobs[job_id]
            job["status"] = status
            self._save(job)

    def _cancelled(self, job_id):
        with self.lock:
            return self.jobs[job_id]["status"] == "cancelled"

    def _work_loop(self):
        while True:
            job_id = self.waiting.get()
            try:
                if self._cancelled(job_id):
                    continue
                self._run_job(job_id)
            except Exception as exc:  # worker phải sống tiếp cho job sau
                with self.lock:
                    job = self.jobs[job_id]
                    if job["status"] != "cancelled":
                        job["status"] = "error"
                        job["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
                        job["payload"] = {}
                        self._save(job)
            finally:
                self.waiting.task_done()

    def _run_job(self, job_id):
        self._set_status(job_id, "running")
        with self.lock:
            payload = self.jobs[job_id]["payload"]
        endpoint = self.endpoint_provider()
        if endpoint is None:
            raise RuntimeError("Forge chưa có /sdapi/v1/txt2img")
        model = self.request_factory(endpoint, payload)
        if hasattr(model, "send_images"):
            model.send_images = True
        if hasattr(model, "save_images"):
            model.save_images = False
        result = self.result_dict(endpoint(model))
        encoded_images = result.get("images") or []
        if not encoded_images:
            raise RuntimeError("Forge không trả ảnh")
        info = result.get("info") or {}
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except ValueError:
                info = {"raw": info}
        files = []
        directory = self._path(job_id)
        for index, encoded in enumerate(encoded_images):
            if self._cancelled(job_id):
                return
            data, extension, mime = _decode_image(encoded)
            name = f"{index:03d}.{extension}"
            path = directory / name
            tmp = directory / f".{name}.tmp"
            tmp.write_bytes(data)
            tmp.replace(path)
            files.append({"name": name, "size": len(data), "mime": mime, "storage": "local"})
        with self.lock:
            job = self.jobs[job_id]
            job["info"] = info
            job["files"] = files
            job["payload"] = {}
            self._save(job)
        if self.storage.configured and not self._cancelled(job_id):
            self._set_status(job_id, "uploading")
            try:
                for item in files:
                    key = f"{self.storage.prefix}/{job_id}/{item['name']}"
                    self.storage.upload(directory / item["name"], key, item["mime"])
                    item["key"] = key
                for item in files:
                    item["storage"] = "s3"
            except Exception as exc:
                with self.lock:
                    self.jobs[job_id]["storage_warning"] = (
                        f"Object storage lỗi ({type(exc).__name__}); đang dùng file local."
                    )
        with self.lock:
            job = self.jobs[job_id]
            if job["status"] != "cancelled":
                job["status"] = "done"
                self._save(job)


def _file_response(request, path, mime):
    """File binary + một Range bytes đơn; stream từng chunk, không đọc cả file vào RAM."""
    from fastapi.responses import FileResponse, StreamingResponse
    from starlette.concurrency import iterate_in_threadpool

    size = path.stat().st_size
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'inline; filename="{path.name}"',
    }
    value = request.headers.get("range", "")
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not value:
        return FileResponse(path, media_type=mime, headers=headers)
    if not match or (not match.group(1) and not match.group(2)):
        return StreamingResponse(iter(()), status_code=416, headers={
            **headers, "Content-Range": f"bytes */{size}",
        })
    if match.group(1):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else size - 1
    else:
        length = int(match.group(2))
        start = max(0, size - length)
        end = size - 1
    end = min(end, size - 1)
    if start >= size or start < 0 or end < start:
        return StreamingResponse(iter(()), status_code=416, headers={
            **headers, "Content-Range": f"bytes */{size}",
        })
    length = end - start + 1

    async def chunks():
        def reader():
            with path.open("rb") as source:
                source.seek(start)
                remaining = length
                while remaining:
                    data = source.read(min(1024 * 1024, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
        async for chunk in iterate_in_threadpool(reader()):
            yield chunk

    return StreamingResponse(chunks(), status_code=206, media_type=mime, headers={
        **headers,
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(length),
    })


def install_mobile_jobs(app, endpoint_provider, request_factory, result_dict,
                        interrupt_provider=None, dependencies=None, job_root=None):
    """Đăng ký job API trên FastAPI; dependencies là auth của route Forge chuẩn."""
    from fastapi import Request
    from fastapi.concurrency import run_in_threadpool
    from fastapi.responses import JSONResponse

    dependencies = list(dependencies or [])
    root = job_root or os.environ.get("ANIME3_MOBILE_JOB_DIR") or \
        Path(__file__).resolve().parents[4] / "colab" / "outputs" / "mobile-jobs"
    manager = MobileJobManager(root, endpoint_provider, request_factory, result_dict,
                               interrupt_provider=interrupt_provider)

    @app.get(f"{API_ROOT}/health", include_in_schema=False, dependencies=dependencies)
    async def health():
        return {
            "ok": True,
            "async_jobs": True,
            "txt2img_available": endpoint_provider() is not None,
            "object_storage": {"configured": manager.storage.configured, "type": "s3"},
        }

    @app.post(f"{API_ROOT}/jobs", include_in_schema=False, dependencies=dependencies)
    async def submit(request: Request):
        try:
            body = await request.json()
            payload = body.get("payload") if isinstance(body, dict) else None
            if not isinstance(payload, dict):
                raise ValueError("payload")
            endpoint = endpoint_provider()
            if endpoint is None:
                return JSONResponse(status_code=503, content={"detail": "Thiếu API txt2img"})
            # Validation trước khi đưa vào queue để client nhận 422 ngay.
            request_factory(endpoint, payload)
            key = str(body.get("idempotency_key") or "")[:160]
            job = await run_in_threadpool(manager.submit, payload, key)
            return JSONResponse(status_code=202, content=job)
        except Exception:
            return JSONResponse(status_code=422, content={"detail": "Payload txt2img không hợp lệ"})

    @app.get(f"{API_ROOT}/jobs/{{job_id}}", include_in_schema=False, dependencies=dependencies)
    async def status(job_id: str):
        job = manager.get(job_id)
        return JSONResponse(status_code=404 if job is None else 200,
                            content=job or {"detail": "Không thấy job"})

    @app.delete(f"{API_ROOT}/jobs/{{job_id}}", include_in_schema=False, dependencies=dependencies)
    async def cancel(job_id: str):
        job = manager.cancel(job_id)
        return JSONResponse(status_code=404 if job is None else 200,
                            content=job or {"detail": "Không thấy job"})

    @app.get(f"{API_ROOT}/jobs/{{job_id}}/result", include_in_schema=False,
             dependencies=dependencies)
    async def result(job_id: str):
        try:
            data = manager.result(job_id)
            return JSONResponse(status_code=404 if data is None else 200,
                                content=data or {"detail": "Không thấy job"})
        except RuntimeError as exc:
            return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get(f"{API_ROOT}/files/{{job_id}}/{{name}}", include_in_schema=False,
             dependencies=dependencies)
    async def download(job_id: str, name: str, request: Request):
        path, mime = manager.file_path(job_id, name)
        if path is None:
            return JSONResponse(status_code=404, content={"detail": "Không thấy file"})
        return _file_response(request, path, mime)

    return manager
