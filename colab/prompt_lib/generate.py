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
PROGRESS_PATHS = ("/sdapi/v1/progress", "/internal/progress")


def _empty_progress(reason="", maybe_busy=False):
    return {"available": False, "source": "", "http_status": 0, "reason": reason,
            "maybe_busy": maybe_busy}


def progress_info(url, timeout=(2.0, 5.0), get=None):
    """Đọc tiến trình Forge, thử **2 endpoint**; trả dict chuẩn hoá.

    `/sdapi/v1/progress` cần bật `--api`; một số bản Forge chỉ có `/internal/progress`
    (endpoint mà chính giao diện Forge dùng). Nếu cả hai đều hỏng, trả
    `{"available": False, "reason": ...}` để UI nói rõ **vì sao** nó không biết tiến trình,
    thay vì hiện "đang chờ Forge trả ảnh…" mãi mà không có thông tin.
    """
    base = str(url or "").rstrip("/")
    if not base:
        return _empty_progress("chưa có địa chỉ Forge")
    get = get or _requests().get
    last_status, last_error, timed_out = 0, "", False
    for path in PROGRESS_PATHS:
        try:
            r = get(f"{base}{path}", params={"skip_current_image": "true"},
                    timeout=timeout)
        except Exception as exc:                  # noqa: BLE001 - chỉ là thông tin phụ
            last_error = type(exc).__name__
            # Không trả lời kịp là dấu hiệu **server đang bận** (GPU giữ GIL / đang nạp
            # model), khác với 404 (endpoint không tồn tại). Phân biệt để không doạ user.
            if "Timeout" in last_error:
                timed_out = True
            continue
        status = int(getattr(r, "status_code", 0) or 0)
        if status != 200:
            last_status = status
            continue
        try:
            data = r.json() or {}
        except Exception:                         # noqa: BLE001
            last_error = "JSON hỏng"
            continue
        if not isinstance(data, dict):
            last_error = "JSON không phải object"
            continue
        return _normalise_progress(data, path)

    if timed_out and not last_status:
        return _empty_progress("Forge không kịp trả lời tiến trình (quá thời gian chờ)",
                               maybe_busy=True)
    reason = (f"HTTP {last_status}" if last_status else "")
    if last_error and not reason:
        reason = last_error
    return _empty_progress(reason or "không đọc được")


def _normalise_progress(data, path):
    """Chuẩn hoá body của một trong hai endpoint tiến trình."""
    state = data.get("state") if isinstance(data.get("state"), dict) else {}

    def number(value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def integer(value):
        return value if type(value) is int else None

    ratio = max(0.0, min(1.0, number(data.get("progress"))))
    job_count = integer(state.get("job_count")) or 0
    step, steps = integer(state.get("sampling_step")), integer(state.get("sampling_steps"))
    return {
        "available": True,
        "source": path,
        "http_status": 200,
        "reason": "",
        "progress": ratio,
        "eta": number(data.get("eta_relative")),
        "job_count": job_count,
        "step": step,
        "steps": steps,
        "interrupted": bool(state.get("interrupted")),
        "busy": job_count > 0 or ratio > 0.001,
        "state": state,
    }


PING_PATHS = ("/sdapi/v1/options", "/sdapi/v1/cmd-flags", "/")


def ping(url, timeout=(2.0, 6.0), get=None):
    """Forge còn phản hồi HTTP không? `{"alive": bool, "status": int, "detail": str}`.

    Thử 3 đường (`options` → `cmd-flags` → `/`) vì khi Forge đang chạy nặng, một endpoint
    có thể quá giờ trong khi server vẫn sống. Dùng để phân biệt *"Forge sống nhưng chưa
    báo bước"* với *"Forge treo/không phản hồi"* — hai triệu chứng giống nhau trên UI.
    """
    base = str(url or "").rstrip("/")
    if not base:
        return {"alive": False, "status": 0, "detail": "chưa có địa chỉ Forge"}
    get = get or _requests().get
    last = {"alive": False, "status": 0, "detail": "không thử được"}
    for path in PING_PATHS:
        try:
            r = get(f"{base}{path}", timeout=timeout)
        except Exception as exc:                  # noqa: BLE001
            last = {"alive": False, "status": 0,
                    "detail": f"{type(exc).__name__}"}
            continue
        status = int(getattr(r, "status_code", 0) or 0)
        # 401/403 vẫn chứng minh server sống (có auth/đang chặn đường đó).
        if status in (200, 401, 403):
            return {"alive": True, "status": status, "path": path,
                    "detail": f"Forge trả lời {path}"}
        last = {"alive": False, "status": status, "detail": f"HTTP {status}"}
    return last


def log_path(env=None):
    """Đường dẫn forge.log: `WAI_LOG`, rồi `/content/forge.log`, rồi `./forge.log`."""
    env = env or os.environ
    candidates = [env.get("WAI_LOG"), env.get("FORGE_LOG"),
                  "/content/forge.log", os.path.join(os.getcwd(), "forge.log")]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


def api_flags(url, timeout=(2.0, 6.0), get=None):
    """`/sdapi/v1/cmd-flags` — phân biệt "Forge thiếu endpoint tiến trình" với "Forge khác API".

    Endpoint này chỉ có khi server chạy `--api`; trả 404 nghĩa là bản Forge đó không phải
    API kiểu A1111 (hoặc `--api` tắt). Dùng trong chẩn đoán, không dùng trong vòng chờ.
    """
    base = str(url or "").rstrip("/")
    if not base:
        return {"available": False, "reason": "chưa có địa chỉ Forge"}
    get = get or _requests().get
    try:
        r = get(f"{base}/sdapi/v1/cmd-flags", timeout=timeout)
    except Exception as exc:                      # noqa: BLE001
        return {"available": False, "reason": type(exc).__name__}
    status = int(getattr(r, "status_code", 0) or 0)
    if status != 200:
        return {"available": False, "reason": f"HTTP {status}"}
    try:
        data = r.json() or {}
    except Exception:                             # noqa: BLE001
        return {"available": False, "reason": "JSON hỏng"}
    if not isinstance(data, dict):
        return {"available": False, "reason": "JSON không phải object"}
    return {"available": True, "api_only": bool(data.get("api_only")),
            "now": bool(data.get("now"))}


LOG_SIGNATURES = (
    ("out of memory", "Hết VRAM (CUDA out of memory)"),
    ("no checkpoints found", "Không tìm thấy checkpoint"),
    ("loading", "Đang nạp checkpoint/model"),
    ("traceback", "Có traceback"),
)


def log_hint(path=None):
    """Đọc cuối forge.log, chỉ trả **loại lỗi** đã lọc (không in message/token/prompt)."""
    path = path if path is not None else log_path()
    if not path or not os.path.exists(path):
        return {"co_log": False, "path": "", "lines": []}
    try:
        with open(path, "rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 64 * 1024))
            text = stream.read(64 * 1024).decode("utf-8", errors="replace")
    except OSError:
        return {"co_log": False, "path": str(path), "lines": []}
    lines = [line.strip() for line in text.splitlines() if line.strip()][-40:]
    found = []
    for needle, label in LOG_SIGNATURES:
        if any(needle in line.lower() for line in lines):
            found.append(label)
    return {"co_log": True, "path": str(path), "lines": found}


def wait_diagnosis(url, elapsed=0, info=None, log=None, ping_result=None, flags=None):
    """Chẩn đoán khi app đang "chờ Forge trả ảnh": trả list dòng Markdown để hiện cho user.

    Không bao giờ in prompt/token/URL riêng tư; chỉ trạng thái endpoint và loại lỗi log.
    """
    info = info if info is not None else progress_info(url)
    ping_result = ping_result if ping_result is not None else ping(url)
    log = log if log is not None else log_hint()
    out = [f"**Chẩn đoán lúc {format_duration(elapsed)} sau khi gửi prompt**"]
    clock = f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}"

    if info.get("busy"):
        out.append(f"✅ `/progress` báo **đang chạy**: {int(round((info.get('progress') or 0) * 100))}%"
                   + (f", bước {info['step']}/{info['steps']}" if info.get("step") is not None
                      and info.get("steps") else "")
                   + (f", còn ~{format_duration(info['eta'])}" if info.get("eta") else "")
                   + f". Nguồn: `{info.get('source') or '/sdapi/v1/progress'}`. "
                   "Nếu thấy đứng ở một % quá lâu thì là VRAM swap, không phải app treo.")
    elif info.get("available"):
        out.append(f"⚪ `/progress` trả lời nhưng **chưa có job nào chạy** "
                   f"(`job_count=0`) ở phút {clock}. Nghĩa là request đã tới Forge nhưng "
                   "**chưa được bắt đầu**: thường do đang nạp checkpoint, hoặc một job khác "
                   "giữ model lock.")
    elif info.get("maybe_busy"):
        out.append("🟡 `/progress` và `/internal/progress` **không trả lời kịp** — dấu hiệu "
                   "server đang bận (GPU/CPU bão hoà khi Hires hoặc swap VRAM). Ảnh vẫn "
                   "đang được tạo; chỉ không có số %.")
    else:
        reason = info.get("reason") or "không rõ"
        out.append(f"❌ Không đọc được tiến trình từ cả `/sdapi/v1/progress` và "
                   f"`/internal/progress` ({reason}). App vẫn chờ ảnh trả về, chỉ không vẽ "
                   "được thanh %.")
        flags = flags if flags is not None else api_flags(url)
        if flags.get("available"):
            out.append("✅ `/sdapi/v1/cmd-flags` trả lời → server đúng chuẩn A1111/Forge API, "
                       "chỉ riêng endpoint tiến trình hỏng. Có thể dùng bản Forge cũ/khác "
                       "nhánh; % sẽ không hiện nhưng ảnh vẫn sinh bình thường.")
        else:
            out.append(f"❌ `/sdapi/v1/cmd-flags` cũng không có ({flags.get('reason')}) → "
                       "server này **không phải A1111/Forge API** hoặc chưa bật `--api`. "
                       "Thêm `--api` vào lệnh chạy Forge rồi khởi động lại.")

    if ping_result.get("alive"):
        out.append(f"✅ Forge **còn phản hồi** HTTP (`{ping_result.get('detail')}`).")
    else:
        out.append(f"❌ Forge **không phản hồi** (`{ping_result.get('detail')}`). Đây là dấu "
                   "hiệu treo thật: VRAM swap hoặc process chết. Bấm **⛔ Huỷ job**, rồi xem "
                   "log và restart Forge.")

    if log.get("co_log"):
        if log.get("lines"):
            out.append("📄 `forge.log` (chỉ loại lỗi, không in nội dung): "
                       + ", ".join(f"**{line}**" for line in log["lines"]))
        else:
            out.append("📄 `forge.log` không có dấu hiệu lỗi trong 40 dòng cuối — "
                       "nhiều khả năng Forge đang chạy bình thường nhưng chậm.")
    else:
        out.append("📄 Không đọc được `forge.log` từ máy này (app chạy trên máy khác?). "
                   "Trên Colab: `/content/forge.log`.")

    if not info.get("busy") and elapsed >= 45:
        out.append("👉 Việc nên làm: (1) chờ thêm 1–2 phút nếu đây là lần sinh đầu tiên "
                   "(`job_count=0` lúc nạp model là bình thường); (2) nếu quá 3 phút vẫn "
                   "`job_count=0`, bấm **⛔ Huỷ job** rồi chạy `install.sh --diagnostics`; "
                   "(3) nếu Forge không phản hồi, restart bằng "
                   "`bash /content/install.sh --only launch,verify --restart`.")
    return out


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
    """Dòng trạng thái: `⏳ 01:12 · bước 9/25 (36%) · còn ~1m 20s`.

    Ba trạng thái được phân biệt rõ — điểm quan trọng nhất để không thấy "treo":
    * đang chạy bước (có `step/steps` hoặc %) → hiện % + ETA;
    * Forge đã nhận nhưng **chưa bắt đầu job** (`job_count=0`) → nói rõ đang nạp model/xếp hàng;
    * **không đọc được tiến trình** → nói rõ endpoint nào hỏng, kèm gợi ý Chẩn đoán.
    """
    info = info or {}
    clock = f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}"
    parts = [f"⏳ **{clock}**"]
    if info.get("busy"):
        if info.get("step") is not None and info.get("steps"):
            parts.append(f"bước {info['step']}/{info['steps']}")
            parts.append(f"({int(round(info['progress'] * 100))}%)")
        else:
            parts.append(f"{int(round(info['progress'] * 100))}%")
        if info.get("eta"):
            parts.append(f"còn ~{format_duration(info['eta'])}")
    elif not info.get("available"):
        reason = info.get("reason") or "không rõ"
        if info.get("maybe_busy"):
            # Server không kịp trả lời endpoint tiến trình — thường vì đang chạy nặng.
            parts.append("Forge **đang chạy** (không kịp trả lời số bước)")
            parts.append("ảnh vẫn đang được tạo — chờ tiếp, đừng bấm lại")
        else:
            parts.append(f"đã gửi prompt, **chưa đọc được tiến trình** ({reason})")
            parts.append("bấm **🔎 Chẩn đoán** để biết Forge có đang chạy không")
    else:
        parts.append("đã gửi prompt, Forge **chưa bắt đầu job**")
        parts.append("(đang nạp checkpoint/xếp hàng)" if elapsed < 120
                     else "quá 2 phút — bấm **🔎 Chẩn đoán**")
    if note:
        parts.append(note)
    return " · ".join(parts)


def advice_for(elapsed, info=None, stalled=0):
    """Lời khuyên theo tình trạng: chưa nhích bước / bước chậm / đang chờ / không đọc được."""
    info = info or {}
    if not info.get("busy"):
        if not info.get("available") and info.get("maybe_busy") and elapsed >= 25:
            return ("ℹ️ Endpoint tiến trình không trả lời kịp — với Forge đang chạy nặng "
                    "(Hires/VRAM swap) đây là bình thường. Ảnh vẫn được tạo; nếu quá 10 phút "
                    "hoặc Forge không phản hồi gì thì bấm **⛔ Huỷ job** rồi xem **🔎 Chẩn đoán**.")
        if not info.get("available") and elapsed >= 20:
            reason = info.get("reason") or "không rõ"
            return (f"⚠️ Không đọc được tiến trình ({reason}). App **vẫn đang chờ ảnh**, chỉ "
                    "không có số %. Bấm **🔎 Chẩn đoán** để kiểm tra Forge còn sống và đọc "
                    "log; nếu Forge không phản hồi thì bấm **⛔ Huỷ job** rồi restart.")
        if elapsed >= 30:
            return ("ℹ️ Forge đã nhận prompt nhưng **chưa bắt đầu job** — lần sinh đầu tiên "
                    "còn nạp checkpoint (6–7 GB) nên mất 1–2 phút. Quá 3 phút vẫn ở đây thì "
                    "bấm **🔎 Chẩn đoán** (có thể job khác đang giữ model lock).")
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

    def progress(self, get=None, timeout=(2.0, 5.0)):
        """Tiến trình Forge + tự đếm thời gian không nhích bước (`stalled`)."""
        info = progress_info(self.base, timeout=timeout, get=get) if self.base else \
            _empty_progress("chưa có địa chỉ Forge")
        step = (info.get("step"), info.get("progress"), info.get("available"))
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
