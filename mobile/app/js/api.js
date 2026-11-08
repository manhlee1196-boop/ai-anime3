/**
 * Gọi API của Forge Neo / A1111 từ điện thoại.
 *
 * Ba nguyên tắc của transport mobile:
 * 1. `POST /vi-mobile/api/jobs` trả job_id ngay; poll trạng thái và tiến trình song song,
 *    không giữ request trong suốt thời gian GPU chạy và không POST lại khi mất kết nối.
 * 2. Manifest chỉ chứa metadata; ảnh tải bằng signed URL/local Range thành Blob. Retry
 *    download độc lập với generation; Huỷ gọi DELETE đúng job_id.
 * 3. Lỗi được dịch sang việc cần làm (tiếng Việt) thay vì "Failed to fetch". */

import { apiUrl, explainError, normalizeBaseUrl } from './core.js';

// `/internal/progress` là route POST của Forge (không phải GET như API A1111).
// Dùng đúng method ngay từ đầu để tránh HTTP 405; body JSON báo không cần ảnh xem trước.
const PROGRESS_PATHS = [
  { path: 'sdapi/v1/progress', method: 'GET' },
  { path: 'internal/progress', method: 'POST', body: { skip_current_image: true } },
];
const PING_PATHS = ['sdapi/v1/options', 'sdapi/v1/cmd-flags'];
// Luồng duy nhất: job nền có id + manifest + file binary. Không fallback base64.
const JOB_API_ROOT = 'vi-mobile/api';

/** Lỗi có thông điệp tiếng Việt + mã HTTP (0 = lỗi mạng). */
export class ForgeError extends Error {
  constructor(message, { status = 0, body = '' } = {}) {
    super(message);
    this.name = 'ForgeError';
    this.status = status;
    this.body = body;
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
      // Header có thể là 200 nhưng thân JSON bị đứt giữa chừng.
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
      throw new ForgeError(
        'Máy chủ trả về HTML thay vì JSON — thường là link tunnel đã hết hạn hoặc '
        + 'Forge chưa bật --api.', { status: response.status, body: text.slice(0, 300) });
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
      {
        path: 'vi-mobile/api/health', method: 'GET', label: 'Job nền & file stream',
        optional: true,
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
          : check.path === 'vi-mobile/api/health'
            ? data?.async_jobs
              ? `Job nền · ${data?.object_storage?.configured ? 'S3/R2' : 'file local'}`
              : 'Cần cập nhật Colab để dùng job nền'
            : Array.isArray(data) ? `${data.length} mục` : 'Phản hồi JSON hợp lệ';
        return {
          ...check,
          ok: true,
          status: 200,
          detail,
          asyncJobs: check.path === 'vi-mobile/api/health' ? Boolean(data?.async_jobs) : undefined,
        };
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
    const hasAsyncJobs = Boolean(out.find((item) => item.path === 'vi-mobile/api/health')?.asyncJobs);
    return {
      base: this.base || '(cùng origin với trang)',
      anyOk,
      hasApi,
      hasProgress,
      hasAsyncJobs,
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

  /** Tạo job nền và trả Blob tải từ manifest; không gửi/nhận ảnh base64. */
  async txt2img(payload, {
    onProgress = null,
    onJob = null,
    onDownload = null,
    interval = 1500,
    timeout = 3600000,
    signal = null,
    idempotencyKey = '',
  } = {}) {
    const merged = combineSignals([signal]);
    const started = Date.now();
    const deadline = started + timeout;
    let finished = false;
    let downloading = false;
    let jobId = '';
    const polling = (async () => {
      while (!finished) {
        await abortableSleep(interval, merged);
        if (finished || downloading) continue;
        try {
          const info = await this.progress({ signal: merged, timeout: 6000 });
          if (onProgress) onProgress(info, Math.round((Date.now() - started) / 1000));
        } catch (error) {
          if (merged.aborted) break;
          // Lỗi đọc tiến trình không được làm hỏng job hoặc tạo job mới.
        }
      }
    })();

    try {
      const health = await this.request(`${JOB_API_ROOT}/health`, {
        timeout: 8000, signal: merged,
      });
      if (!health?.async_jobs) {
        throw new ForgeError(
          'Colab chưa có job API mới. Chạy lại notebook một ô để cập nhật extension; '
          + 'app sẽ không dùng lại API base64 cũ.', { status: 409 },
        );
      }
      const key = idempotencyKey || makeIdempotencyKey();
      const created = await this.request(`${JOB_API_ROOT}/jobs`, {
        method: 'POST',
        body: { payload, idempotency_key: key },
        timeout: 20000,
        signal: merged,
      });
      jobId = String(created?.job_id || '');
      if (!jobId) throw new ForgeError('Máy chủ không trả job_id.', { status: 202 });
      if (onJob) onJob({ ...created, job_id: jobId, idempotency_key: key });

      let failedStatusReads = 0;
      while (Date.now() < deadline) {
        if (merged.aborted) throw cancelledError();
        let job;
        try {
          job = await this.request(`${JOB_API_ROOT}/jobs/${jobId}`, {
            timeout: 10000, signal: merged,
          });
          failedStatusReads = 0;
        } catch (error) {
          if (merged.aborted || error?.name === 'AbortError') throw cancelledError();
          failedStatusReads += 1;
          if (failedStatusReads >= 5) throw error;
          await abortableSleep(interval, merged);
          continue;
        }
        if (job?.status === 'done') break;
        if (job?.status === 'error') {
          throw new ForgeError(`Job tạo ảnh thất bại: ${job.error || 'lỗi không rõ'}`, {
            status: 500, body: String(job.error || ''),
          });
        }
        if (job?.status === 'cancelled') throw cancelledError();
        await abortableSleep(interval, merged);
      }
      if (Date.now() >= deadline) {
        throw new ForgeError('Đã chờ job quá lâu; dùng job_id để kiểm tra lại, không tạo job mới.', {
          status: 0, body: jobId,
        });
      }

      const manifest = await this.request(`${JOB_API_ROOT}/jobs/${jobId}/result`, {
        timeout: 15000, signal: merged,
      });
      const files = Array.isArray(manifest?.files) ? manifest.files : [];
      if (!files.length) throw new ForgeError('Manifest không có file ảnh.', { status: 200 });
      downloading = true;
      const images = [];
      for (let index = 0; index < files.length; index += 1) {
        const blob = await this.downloadFile(files[index], {
          signal: merged,
          onProgress: (progress) => {
            if (onDownload) onDownload({ ...progress, index, count: files.length, jobId });
          },
        });
        images.push(blob);
      }
      return {
        images,
        info: manifest.info || {},
        elapsed: Math.round((Date.now() - started) / 1000),
        jobId,
        storageWarning: manifest.storage_warning || '',
      };
    } finally {
      finished = true;
      await polling;
    }
  }

  /** Huỷ đúng job; server chỉ interrupt job đang chạy, bỏ queued job khỏi worker. */
  async cancelJob(jobId, { signal = null } = {}) {
    return this.request(`${JOB_API_ROOT}/jobs/${jobId}`, {
      method: 'DELETE', timeout: 8000, signal,
    });
  }

  /** Tải binary có tiến trình + tối đa 3 lượt resume Range; không liên quan job GPU. */
  async downloadFile(file, { signal = null, onProgress = null } = {}) {
    const absolute = /^https?:\/\//i.test(file.url);
    const url = absolute ? file.url : this.url(file.url);
    const sameForge = !absolute || (this.base && url.startsWith(`${this.base}/`));
    const expected = Number(file.size) || 0;
    let loaded = 0;
    let chunks = [];
    let lastError = null;

    for (let attempt = 0; attempt < 3; attempt += 1) {
      const controller = new AbortController();
      const merged = combineSignals([controller.signal, signal]);
      const timer = setTimeout(() => controller.abort(new Error('download timeout')), 120000);
      try {
        const headers = sameForge ? this.headers({ Accept: file.mime || '*/*' }) : {};
        if (loaded > 0) headers.Range = `bytes=${loaded}-`;
        const response = await this.fetch(url, {
          method: 'GET', headers, signal: merged, credentials: 'omit', cache: 'no-store',
        });
        if (response.status === 416 && expected && loaded >= expected) {
          return new Blob(chunks, { type: file.mime || 'application/octet-stream' });
        }
        if (!response.ok) {
          throw new ForgeError(`Tải file thất bại (HTTP ${response.status}).`, {
            status: response.status, body: await response.text(),
          });
        }
        // Server không nhận Range thì phải đọc lại từ đầu, không nối trùng byte.
        if (loaded > 0 && response.status !== 206) {
          chunks = [];
          loaded = 0;
        }
        if (response.body?.getReader) {
          const reader = response.body.getReader();
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
            loaded += value.byteLength;
            if (onProgress) onProgress({ loaded, total: expected || loaded });
          }
        } else {
          const blob = await response.blob();
          chunks.push(blob);
          loaded += blob.size;
          if (onProgress) onProgress({ loaded, total: expected || loaded });
        }
        if (expected && loaded !== expected) {
          throw new ForgeError(`File thiếu byte: ${loaded}/${expected}.`, { status: 0 });
        }
        return new Blob(chunks, { type: file.mime || 'application/octet-stream' });
      } catch (error) {
        lastError = error;
        if (signal?.aborted || error?.name === 'AbortError' && signal?.aborted) {
          throw cancelledError();
        }
        if (Number(error?.status) >= 400 && Number(error?.status) < 500
          && Number(error?.status) !== 416) throw error;
        if (attempt < 2) await abortableSleep(400 * (attempt + 1), signal);
      } finally {
        clearTimeout(timer);
      }
    }
    throw new ForgeError(
      `Không tải được ${file.name || 'ảnh'} sau 3 lượt. Job đã xong; chỉ cần thử tải lại file.`,
      { status: Number(lastError?.status) || 0, body: String(lastError?.message || lastError) },
    );
  }

}

function makeIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

function abortableSleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(cancelledError());
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', abort);
      resolve();
    }, ms);
    const abort = () => {
      clearTimeout(timer);
      reject(cancelledError());
    };
    signal?.addEventListener('abort', abort, { once: true });
  });
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
