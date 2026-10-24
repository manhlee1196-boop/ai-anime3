"""Sinh ảnh qua API Forge mà **không treo** UI: timeout tách, tiến trình, chẩn đoán, huỷ.

Vì sao app "treo" khi bấm *Sinh ảnh*:

1. `requests.post(..., timeout=1800)` đặt **cùng một giới hạn cho connect và read**, nên
   khi Forge kẹt (nạp checkpoint lần đầu, hết VRAM ở Hires, job cũ chưa xong) app đứng
   tới 30 phút mà không nói gì.
2. Một request `txt2img` là **đồng bộ**: Forge chỉ trả lời khi xong ảnh. Trên T4, 25 bước
   832×1216 + Hires 1.5× có thể 3–6 phút → nhìn như treo dù vẫn chạy.
3. Không có nút **Huỷ**, không đọc `/sdapi/v1/progress`, nên người dùng không phân biệt
   được "đang chạy chậm" với "đã kẹt".

Module này bọc request trong một luồng riêng và cung cấp:

* `timeouts()` — `(connect, read)`, read lấy từ `WAI_GEN_TIMEOUT` (mặc định 900 giây).
* `GenerationJob` — chạy POST ở thread nền, `.done`, `.elapsed`, `.progress()`.
* `progress_info(url)` — đọc `/sdapi/v1/progress` (bước hiện tại, ETA, job_count).
* `interrupt(url)` — gọi `/sdapi/v1/interrupt` để dừng job đang kẹt.
* `status_line`, `advice_for` — câu thông báo tiếng Việt cho UI.

Thuần stdlib + `requests` (import muộn để test được mà không cần mạng).
"""

import os
import threading
import time

DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 900          # 15 phút: đủ cho Hires trên T4, ngắn hơn 30 phút cũ
MIN_READ_TIMEOUT = 60
MAX_READ_TIMEOUT = 3600
STALL_SECONDS = 90                  # không nhích bước bao lâu thì cảnh báo


def _requests():
    import requests
    return requests


# --------------------------------------------------------------------- timeout
def read_timeout(env=None):
    """Giới hạn chờ Forge trả ảnh (giây), chỉnh bằng `WAI_GEN_TIMEOUT`."""
    raw = str((env or os.environ).get("WAI_GEN_TIMEOUT", "") or "").strip()
    if raw:
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            value = 0
        if value:
            return max(MIN_READ_TIMEOUT, min(MAX_READ_TIMEOUT, value))
    return DEFAULT_READ_TIMEOUT


def timeouts(env=None):
    """`(connect, read)` cho requests — connect ngắn để biết ngay Forge có sống không."""
    return (DEFAULT_CONNECT_TIMEOUT, read_timeout(env))


# --------------------------------------------------------------------- tiến trình
def progress_info(url, timeout=3.0, get=None):
    """Đọc `/sdapi/v1/progress`. Trả dict chuẩn hoá; `{}` nếu không đọc được.

    Forge/A1111 trả: `progress` (0..1), `eta_relative`, `state.job_count`,
    `state.sampling_step`, `state.sampling_steps`, `state.interrupted`.
    """
    base = str(url or "").rstrip("/")
    if not base:
        return {}
    get = get or _requests().get
    try:
        r = get(f"{base}/sdapi/v1/progress", params={"skip_current_image": "true"},
                timeout=timeout)
        if getattr(r, "status_code", 0) != 200:
            return {}
        data = r.json() or {}
    except Exception:                             # noqa: BLE001 - chỉ là thông tin phụ
        return {}
    if not isinstance(data, dict):
        return {}
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    try:
        ratio = float(data.get("progress") or 0.0)
    except (TypeError, ValueError):
        ratio = 0.0
    try:
        eta = float(data.get("eta_relative") or 0.0)
    except (TypeError, ValueError):
        eta = 0.0
    job_count = state.get("job_count")
    if type(job_count) is not int:
        job_count = 0
    step, steps = state.get("sampling_step"), state.get("sampling_steps")
    step = step if type(step) is int else None
    steps = steps if type(steps) is int else None
    return {
        "progress": max(0.0, min(1.0, ratio)),
        "eta": eta,
        "job_count": job_count,
        "step": step,
        "steps": steps,
        "interrupted": bool(state.get("interrupted")),
        "busy": job_count > 0 or ratio > 0.001,
        "state": state,
    }


def busy_message(info):
    """Câu báo khi Forge đang chạy job khác (bấm sinh ảnh lúc này sẽ phải chờ)."""
    if not info or not info.get("busy"):
        return ""
    percent = int(round((info.get("progress") or 0) * 100))
    eta = info.get("eta") or 0
    tail = f", còn ~{format_duration(eta)}" if eta else ""
    return (f"⏳ Forge đang bận một job khác ({percent}%{tail}). "
            "App sẽ chờ job đó xong rồi mới gửi prompt của bạn.")


def format_duration(seconds):
    """`95` → `1m 35s`, `8` → `8s`."""
    try:
        total = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "?"
    if total < 60:
        return f"{total}s"
    minutes, rest = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def status_line(elapsed, info=None, note=""):
    """Dòng trạng thái: `⏳ 01:12 · bước 9/25 (36%) · còn ~1m 20s`."""
    clock = f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}"
    parts = [f"⏳ **{clock}**"]
    if info and info.get("busy"):
        if info.get("step") is not None and info.get("steps"):
            parts.append(f"bước {info['step']}/{info['steps']}")
            parts.append(f"({int(round(info['progress'] * 100))}%)")
        else:
            parts.append(f"{int(round(info['progress'] * 100))}%")
        if info.get("eta"):
            parts.append(f"còn ~{format_duration(info['eta'])}")
    else:
        parts.append("đang chờ Forge trả ảnh…")
    if note:
        parts.append(note)
    return " · ".join(parts)


def advice_for(elapsed, info=None, stalled=0):
    """Lời khuyên theo tình trạng: chưa nhích bước / bước chậm / đang chạy bình thường."""
    if not info or not info.get("busy"):
        if elapsed >= 30:
            return ("ℹ️ Forge chưa báo tiến trình — lần sinh đầu tiên còn nạp checkpoint "
                    "(6–7 GB) nên có thể mất 1–2 phút trước khi thấy bước.")
        return ""
    if stalled >= STALL_SECONDS:
        return (f"⚠️ Không nhích bước trong {format_duration(stalled)}. Thường do: (1) đang "
                "nạp/đổi checkpoint, (2) hết VRAM ở Hires nên phải swap, (3) job kẹt. "
                "Bấm **⛔ Huỷ job** rồi tắt Hires, giữ 832×1216 và thử lại.")
    return ""


# --------------------------------------------------------------------- huỷ
def interrupt(url, timeout=5.0, post=None):
    """Dừng job Forge đang chạy. Trả `(ok, message)`."""
    base = str(url or "").rstrip("/")
    if not base:
        return False, "❌ Chưa có địa chỉ Forge."
    post = post or _requests().post
    try:
        r = post(f"{base}/sdapi/v1/interrupt", timeout=timeout)
        if getattr(r, "status_code", 0) == 200:
            return True, ("⛔ Đã gửi lệnh huỷ. Job đang chạy sẽ dừng ở bước kế tiếp; "
                          "ảnh dở dang không được trả về.")
    except Exception as exc:                      # noqa: BLE001
        return False, f"❌ Không gửi được lệnh huỷ: `{type(exc).__name__}: {exc}`"
    return False, f"❌ Forge không nhận lệnh huỷ (mã {getattr(r, 'status_code', '?')})."


# --------------------------------------------------------------------- job
class GenerationJob:
    """Chạy `POST /sdapi/v1/txt2img` ở thread nền để UI vẫn cập nhật được trạng thái.

    Dùng:

        job = GenerationJob(url, payload).start()
        while not job.done:
            print(job.elapsed, job.progress(url)["progress"])
            time.sleep(1)
        response, error = job.response, job.error
    """

    def __init__(self, url, payload, timeout=None, post=None):
        self.base = str(url or "").rstrip("/")
        self.endpoint = f"{self.base}/sdapi/v1/txt2img"
        self.payload = payload
        self.timeout = timeout or timeouts()
        self._post = post
        self._thread = None
        self._done = threading.Event()
        self.cancelled = threading.Event()
        self.started = time.time()
        self.finished = None
        self.response = None
        self.error = None
        self._last_step = None
        self._last_change = time.time()

    # -- vòng đời
    def start(self):
        self._thread = threading.Thread(target=self._run, name="wai-generate", daemon=True)
        self._thread.start()
        return self

    def _run(self):
        post = self._post or _requests().post
        try:
            self.response = post(self.endpoint, json=self.payload, timeout=self.timeout)
            if hasattr(self.response, "raise_for_status"):
                self.response.raise_for_status()
        except BaseException as exc:             # noqa: BLE001 - chuyển nguyên cho UI
            self.error = exc
        finally:
            self.finished = time.time()
            self._done.set()

    # -- trạng thái
    @property
    def done(self):
        return self._done.is_set()

    @property
    def elapsed(self):
        return (self.finished or time.time()) - self.started

    def wait(self, timeout=None):
        self._done.wait(timeout)
        return self.done

    def progress(self, get=None, timeout=3.0):
        """Tiến trình Forge + tự đếm thời gian không nhích bước (`stalled`)."""
        info = progress_info(self.base, timeout=timeout, get=get) if self.base else {}
        step = (info.get("step"), info.get("progress"))
        if step != self._last_step:
            self._last_step = step
            self._last_change = time.time()
        info["stalled"] = time.time() - self._last_change
        return info

    def cancel(self):
        """Gửi lệnh huỷ tới Forge; thread vẫn chờ response (Forge trả 500/ảnh dở)."""
        self.cancelled.set()
        return interrupt(self.base)


def payload_warnings(payload, vram_gb=None):
    """Cảnh báo cấu hình dễ kẹt/hết VRAM trước khi gửi job (T4 16 GB)."""
    warnings = []
    width, height = payload.get("width") or 0, payload.get("height") or 0
    try:
        pixels = int(width) * int(height)
    except (TypeError, ValueError):
        pixels = 0
    if payload.get("enable_hr"):
        scale = float(payload.get("hr_scale") or 1.5)
        final = pixels * scale * scale
        if final >= 2_000_000:
            warnings.append(
                f"⚠️ Hires đang bật: ảnh cuối ~{int(scale * width)}×{int(scale * height)} "
                f"({final / 1e6:.1f} MP). T4 16 GB rất dễ kẹt ở bước upscale — lần đầu nên "
                "để Hires **tắt**, dựng bố cục rồi mới bật.")
    if pixels > 1_300_000:
        warnings.append(f"⚠️ {width}×{height} là trên 1,3 MP; SDXL trên T4 nên giữ "
                        "832×1216 hoặc 1024×1024.")
    steps = payload.get("steps")
    if type(steps) is int and steps > 40:
        warnings.append(f"⚠️ {steps} bước là khá nhiều cho SDXL (thẻ model WAI ghi 15–30); "
                        "nhiều bước không thêm chi tiết mà chỉ làm lâu.")
    return warnings


def describe_error(exc, timeout=None):
    """Câu lỗi tiếng Việt kèm việc cần làm, cho mọi kiểu hỏng của kết nối tới Forge."""
    requests = _requests()
    name = type(exc).__name__
    limit = format_duration(timeout if timeout else read_timeout())
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return (f"⏱️ **Forge không trả lời sau {limit}** — job coi như kẹt.\n\n"
                "Thường do: hết VRAM ở Hires (T4 phải swap), checkpoint lần đầu đang nạp, "
                "hoặc job trước chưa xong. Việc cần làm: bấm **⛔ Huỷ job**, tắt **Hires**, "
                "để 832×1216, `batch=1` rồi thử lại. Cần chờ lâu hơn thì đặt "
                "`WAI_GEN_TIMEOUT=1800` trước khi chạy app.")
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return ("⏱️ Không kết nối được tới Forge trong 10 giây. Forge có thể đang khởi động "
                "(nạp checkpoint lần đầu mất 1–3 phút) — chờ rồi bấm **🔌 Kiểm tra kết nối**.")
    if isinstance(exc, requests.exceptions.ConnectionError):
        return ("❌ Không nối được tới Forge. Kiểm tra: Forge đã chạy với cờ `--api`, cổng "
                "trong ô *Địa chỉ Forge* đúng (mặc định `http://127.0.0.1:7860`), và app "
                "chạy cùng máy/runtime với Forge.")
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 500:
        body = ""
        try:
            body = str(exc.response.json()).lower()
        except (ValueError, TypeError, AttributeError):
            body = str(exc).lower()
        if "out of memory" in body or "cuda oom" in body:
            return ("❌ **Hết VRAM** khi sinh ảnh. Tắt Hires, dùng 832×1216 hoặc 1024×1024, "
                    "`batch=1`; đóng runtime/app khác đang dùng GPU rồi thử lại. Không cần "
                    "tải lại checkpoint.")
        return ("❌ Forge báo lỗi 500 khi sinh ảnh. Xem log Forge; nếu là lần đầu, chờ "
                "checkpoint nạp xong rồi thử lại. Prompt và tham số của bạn vẫn được giữ.")
    if status == 404:
        return ("❌ Forge không có `/sdapi/v1/txt2img` — app chưa bật `--api`. Thêm "
                "`--api` vào lệnh chạy Forge rồi khởi động lại.")
    if isinstance(exc, requests.exceptions.HTTPError):
        return (f"❌ Forge trả mã {status or '?'}. Kiểm tra log Forge và bấm "
                "**🔌 Kiểm tra kết nối**.")
    return f"❌ Sinh ảnh thất bại (`{name}`). Prompt và tham số của bạn vẫn được giữ."
