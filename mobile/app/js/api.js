/**
 * Gọi API của Forge Neo / A1111 từ điện thoại.
 *
 * Ba việc quan trọng mà bản web hay làm sai, ở đây làm đúng:
 * 1. `POST /sdapi/v1/txt2img` là **đồng bộ** — Forge chỉ trả lời khi ảnh xong. Vì vậy
 *    request chạy song song với việc đọc `/sdapi/v1/progress`, không có timeout cứng
 *    kiểu 30 giây (ảnh Hires trên T4 mất 3–6 phút là bình thường).
 * 2. **Huỷ** gọi `/sdapi/v1/interrupt` rồi bỏ request, để không mất GPU slot.
 * 3. Lỗi được dịch sang việc cần làm (tiếng Việt) thay vì "Failed to fetch".
 */

import { apiUrl, explainError, normalizeBaseUrl } from './core.js';

// `/internal/progress` là route POST của Forge (không phải GET như API A1111).
// Dùng đúng method ngay từ đầu để tránh HTTP 405; body JSON báo không cần ảnh xem trước.
const PROGRESS_PATHS = [
  { path: 'sdapi/v1/progress', method: 'GET' },
  { path: 'internal/progress', method: 'POST', body: { skip_current_image: true } },
];
const PING_PATHS = ['sdapi/v1/options', 'sdapi/v1/cmd-flags'];

/** Lỗi có thông điệp tiếng Việt + mã HTTP (0 = lỗi mạng). */
export class ForgeError extends Error {
  constructor(message, { status = 0, body = '', incomplete = false } = {}) {
    super(message);
    this.name = 'ForgeError';
    this.status = status;
    this.body = body;
    this.incomplete = incomplete;
  }
}

function cancelledError() {
  const error = new ForgeError('Đã huỷ job.');
  error.name = 'AbortError';
  return error;
}

function encodeBasicAuth(user, pass) {
  const raw = `${user}:${pass}`;
  // btoa chỉ nhận latin1 — tài khoản thường là ASCII, còn lại thì mã hoá UTF-8.
  const bytes = new TextEncoder().encode(raw);
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return `Basic ${btoa(binary)}`;
}

function combineSignals(signals) {
  const controller = new AbortController();
  for (const signal of signals) {
    if (!signal) continue;
    if (signal.aborted) {
      controller.abort(signal.reason);
      break;
    }
    signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true });
  }
  return controller.signal;
}

export class ForgeClient {
  constructor({ base = '', user = '', pass = '', fetchImpl = null } = {}) {
    this.base = normalizeBaseUrl(base);
    this.user = user || '';
    this.pass = pass || '';
    this.fetch = fetchImpl || ((...args) => fetch(...args));
  }

  url(path) {
    return apiUrl(this.base, path);
  }

  headers(extra = {}) {
    const headers = { Accept: 'application/json', ...extra };
    if (this.user) headers.Authorization = encodeBasicAuth(this.user, this.pass);
    return headers;
  }

  /** GET/POST có timeout ngắn (chỉ dùng cho các lệnh nhẹ, không dùng cho sinh ảnh). */
  async request(path, { method = 'GET', body = null, timeout = 15000, signal = null } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error('timeout')), timeout);
    const merged = combineSignals([controller.signal, signal]);
    let response;
    try {
      response = await this.fetch(this.url(path), {
        method,
        headers: this.headers(body ? { 'Content-Type': 'application/json' } : {}),
        body: body ? JSON.stringify(body) : undefined,
        signal: merged,
        credentials: 'omit',
        mode: 'cors',
        cache: 'no-store',
      });
    } catch (error) {
      clearTimeout(timer);
      if (signal?.aborted) throw cancelledError();
      const aborted = error?.name === 'AbortError';
      throw new ForgeError(
        aborted ? 'Hết thời gian chờ máy chủ.' : explainError(0),
        { status: 0, body: String(error?.message || error) },
      );
    }
    let text;
    try {
      text = await response.text();
    } catch (error) {
      clearTimeout(timer);
      if (signal?.aborted) throw cancelledError();
      // Header có thể là 200 nhưng thân JSON chứa ảnh bị đứt giữa chừng.
      throw new ForgeError(explainError(0), {
        status: 0,
        body: `Mất kết nối khi đọc nội dung phản hồi: ${String(error?.message || error)}`,
      });
    }
    clearTimeout(timer);
    if (!response.ok) {
      throw new ForgeError(explainError(response.status, text),
        { status: response.status, body: text });
    }
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch (error) {
      // Một số WebView/proxy trả text đã cắt thay vì reject response.text(). Chỉ xem là
      // response ảnh đứt khi đúng route txt2img và phần đầu đã có trường images; HTML
      // của tunnel hết hạn vẫn phải báo lỗi ngay, không chờ khôi phục ba phút.
      const incomplete = path === 'sdapi/v1/txt2img'
        && /^\s*\{\s*"images"\s*:/.test(text);
      throw new ForgeError(
        incomplete
          ? 'Nội dung ảnh bị cắt giữa chừng — đang thử lấy lại kết quả từ Forge.'
          : 'Máy chủ trả về HTML thay vì JSON — thường là link tunnel đã hết hạn hoặc '
            + 'Forge chưa bật --api.',
        {
          status: incomplete ? 0 : response.status,
          body: text.slice(0, 300),
          incomplete,
        });
    }
  }

  /** Kiểm tra kết nối + lấy thông tin model/flag. */
  async ping() {
    let last = null;
    for (const path of PING_PATHS) {
      try {
        const data = await this.request(path, { timeout: 8000 });
        const model = data?.sd_model_checkpoint || data?.sd_checkpoint || '';
        return { ok: true, path, model: String(model), flags: path.includes('cmd-flags') ? data : null };
      } catch (error) {
        last = error;
      }
    }
    throw last || new ForgeError(explainError(0));
  }

  async options() {
    return this.request('sdapi/v1/options', { timeout: 10000 });
  }

  async samplers() {
    const list = await this.request('sdapi/v1/samplers', { timeout: 10000 });
    return Array.isArray(list) ? list.map((item) => item.name).filter(Boolean) : [];
  }

  async upscalers() {
    const list = await this.request('sdapi/v1/upscalers', { timeout: 10000 });
    return Array.isArray(list) ? list.map((item) => item.name).filter(Boolean) : [];
  }

  /** Tiến trình hiện tại; thử API chuẩn rồi route POST nội bộ của Forge. */
  async progress({ signal = null, timeout = 6000 } = {}) {
    for (const endpoint of PROGRESS_PATHS) {
      try {
        const path = endpoint.method === 'GET'
          ? `${endpoint.path}?skip_current_image=true`
          : endpoint.path;
        const data = await this.request(path, {
          method: endpoint.method,
          body: endpoint.body || null,
          timeout,
          signal,
        });
        return normaliseProgress(data, endpoint.path);
      } catch (error) {
        if (error?.name === 'AbortError') throw error;
      }
    }
    return { available: false, progress: 0, step: 0, steps: 0, eta: 0 };
  }

  /**
   * Chẩn đoán nhanh: gọi song song các endpoint quan trọng, giữ nguyên thứ tự kết quả.
   * `/internal/progress` là phương án dự phòng và bắt buộc POST trên Forge.
   */
  async diagnose() {
    const checks = [
      { path: 'sdapi/v1/options', method: 'GET', label: 'Cấu hình & checkpoint' },
      { path: 'sdapi/v1/cmd-flags', method: 'GET', label: 'Cờ khởi động Forge' },
      { path: 'sdapi/v1/sd-models', method: 'GET', label: 'Danh sách model' },
      {
        path: 'sdapi/v1/progress', method: 'GET', label: 'Tiến trình chuẩn',
        query: '?skip_current_image=true',
      },
      {
        path: 'internal/progress', method: 'POST', label: 'Tiến trình Forge (dự phòng)',
        body: { skip_current_image: true }, optional: true,
      },
    ];
    const out = await Promise.all(checks.map(async (check) => {
      try {
        const data = await this.request(`${check.path}${check.query || ''}`, {
          method: check.method,
          body: check.body || null,
          timeout: 7000,
        });
        const detail = check.path.endsWith('options')
          ? String(data?.sd_model_checkpoint || '(không rõ model)').split(/[\\/]/).pop()
          : Array.isArray(data) ? `${data.length} mục` : 'Phản hồi JSON hợp lệ';
        return { ...check, ok: true, status: 200, detail };
      } catch (error) {
        return {
          ...check,
          ok: false,
          status: Number(error?.status) || 0,
          detail: error.message,
        };
      }
    }));
    const anyOk = out.some((item) => item.ok);
    const hasApi = Boolean(out.find((item) => item.path === 'sdapi/v1/options')?.ok);
    const hasProgress = out.some((item) => item.path.endsWith('progress') && item.ok);
    return {
      base: this.base || '(cùng origin với trang)',
      anyOk,
      hasApi,
      hasProgress,
      checks: out,
    };
  }

  /** Dừng job đang chạy trên Forge. */
  async interrupt() {
    try {
      await this.request('sdapi/v1/interrupt', { method: 'POST', timeout: 8000 });
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Sinh ảnh: POST txt2img + đọc tiến trình song song.
   * Trả về `{images, info}`; `images` là data URL dùng ngay được trong <img>.
   */
  async txt2img(payload, {
    onProgress = null,
    onRecover = null,
    interval = 1500,
    recoveryTimeout = 180000,
    signal = null,
  } = {}) {
    const controller = new AbortController();
    const merged = combineSignals([controller.signal, signal]);
    let finished = false;
    let latestInfo = null;
    let latestPreview = null;
    let previewRequested = false;
    const started = Date.now();
    const poll = async () => {
      while (!finished) {
        await new Promise((resolve) => setTimeout(resolve, interval));
        if (finished) break;
        try {
          const info = await this.progress({ signal: merged, timeout: 6000 });
          latestInfo = info;
          if (onProgress) onProgress(info, Math.round((Date.now() - started) / 1000));
          // Chỉ tải preview một lần gần cuối, tránh gửi base64 lớn trong mọi lượt poll.
          if (!previewRequested && info.progress >= 0.9) {
            previewRequested = true;
            const preview = await this.progressImage({ signal: merged });
            if (preview?.image) latestPreview = preview;
          }
        } catch (error) {
          if (finished) break;
        }
      }
    };
    const polling = poll();

    let data;
    let requestError = null;
    try {
      data = await this.request('sdapi/v1/txt2img', {
        method: 'POST',
        body: payload,
        timeout: 3600000,          // 60 phút: chỉ để không treo vô hạn, không phải "timeout ảnh"
        signal: merged,
      });
    } catch (error) {
      requestError = error;
    } finally {
      finished = true;
      await polling;
    }

    if (requestError) {
      // Huỷ là thao tác chủ động: không chờ khôi phục và không hiện ảnh sau Huỷ.
      // (Kiểm tra cả signal vì WebView có thể gói AbortError thành lỗi mạng.)
      if (merged.aborted || requestError?.name === 'AbortError') throw requestError;
      const recoverable = requestError?.incomplete
        || [0, 502, 503, 504].includes(Number(requestError?.status));
      if (!recoverable) throw requestError;
      if (onRecover) onRecover();
      // Không POST lại: Forge có thể đã xong hoặc vẫn đang chạy, POST lại sẽ nhân đôi job.
      const recovered = await this.recoverGeneratedImage({
        previousInfo: latestInfo,
        previousImage: latestPreview,
        signal: merged,
        timeout: recoveryTimeout,
      });
      if (recovered) {
        const info = {
          prompt: payload.prompt || '',
          negative_prompt: payload.negative_prompt || '',
          width: payload.width,
          height: payload.height,
          steps: payload.steps,
          sampler_name: payload.sampler_name,
          cfg_scale: payload.cfg_scale,
          recovered_from_progress: true,
        };
        if (Number(payload.seed) >= 0) info.seed = Number(payload.seed);
        return {
          images: [toDataUrl(recovered.image)],
          info,
          elapsed: Math.round((Date.now() - started) / 1000),
          recovered: true,
        };
      }
      if (Number(requestError?.status) === 0) {
        throw new ForgeError(
          'Mất kết nối khi tải ảnh kết quả. API vẫn hoạt động nhưng gói ảnh lớn bị đứt. '
          + 'Job có thể đã xong; không tạo lại ngay. Kiểm tra output của Forge, rồi tắt Hires '
          + 'hoặc giảm kích thước trước khi thử lại.',
          { status: 0, body: requestError.body || '' },
        );
      }
      throw requestError;
    }

    const images = Array.isArray(data?.images) ? data.images.filter(Boolean) : [];
    if (!images.length) {
      throw new ForgeError('Forge không trả ảnh nào — kiểm tra forge.log.', { status: 200 });
    }
    return {
      images: images.map(toDataUrl),
      info: parseInfo(data.info),
      elapsed: Math.round((Date.now() - started) / 1000),
    };
  }

  /** Đọc preview cuối từ progress sau khi response txt2img bị đứt; không tạo job mới. */
  async recoverGeneratedImage({
    previousInfo = null, previousImage = null, signal = null, timeout = 180000,
  } = {}) {
    if (signal?.aborted) return null;
    if (previousImage?.image && Number(previousInfo?.progress) >= 0.9) return previousImage;
    const deadline = Date.now() + timeout;
    let sawJob = Boolean(previousInfo && (previousInfo.jobCount > 0 || previousInfo.progress > 0));
    let failedRounds = 0;
    while (Date.now() < deadline && !signal?.aborted) {
      const snapshot = await this.progressImage({ signal });
      if (!snapshot) {
        failedRounds += 1;
        if (failedRounds >= 2) return null;
      } else {
        failedRounds = 0;
        const { info, image } = snapshot;
        sawJob = sawJob || info.jobCount > 0 || info.progress > 0;
        const nearFinal = info.progress >= 0.85 || Number(previousInfo?.progress) >= 0.85;
        const finished = sawJob && info.jobCount === 0 && info.progress === 0;
        if (image && (nearFinal || finished)) return { image, info };
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    return null;
  }

  /** Một lượt progress có current_image; lỗi trả null để còn thử endpoint/lượt khác. */
  async progressImage({ signal = null } = {}) {
    let withoutImage = null;
    for (const endpoint of PROGRESS_PATHS) {
      try {
        const path = endpoint.method === 'GET'
          ? `${endpoint.path}?skip_current_image=false`
          : endpoint.path;
        const data = await this.request(path, {
          method: endpoint.method,
          body: endpoint.method === 'POST' ? { skip_current_image: false } : null,
          timeout: 8000,
          signal,
        });
        const info = normaliseProgress(data, endpoint.path);
        const image = typeof data?.current_image === 'string' ? data.current_image : '';
        if (image) return { info, image };
        withoutImage = { info, image: '' };
      } catch (error) {
        if (signal?.aborted) return null;
      }
    }
    return withoutImage;
  }

}

function toDataUrl(encoded) {
  if (typeof encoded !== 'string') return '';
  if (encoded.startsWith('data:')) return encoded;
  return `data:image/png;base64,${encoded}`;
}

function parseInfo(info) {
  if (!info) return {};
  if (typeof info === 'string') {
    try {
      return JSON.parse(info);
    } catch (error) {
      return {};
    }
  }
  return typeof info === 'object' ? info : {};
}

function normaliseProgress(data, source) {
  if (!data || typeof data !== 'object') return { available: false, source, progress: 0 };
  const state = data.state && typeof data.state === 'object' ? data.state : {};
  const progress = Number(data.progress ?? data.percent ?? 0) || 0;
  const step = Number(state.sampling_step ?? data.sampling_step ?? 0) || 0;
  const steps = Number(state.sampling_steps ?? data.sampling_steps ?? 0) || 0;
  const eta = Number(data.eta_relative ?? data.eta ?? 0) || 0;
  const jobCount = Number(state.job_count ?? data.job_count ?? 0) || 0;
  return {
    available: true,
    source,
    progress: progress > 1 ? progress / 100 : progress,
    step,
    steps,
    eta: eta > 0 ? eta : 0,
    jobCount,
    job: String(state.job ?? ''),
  };
}
