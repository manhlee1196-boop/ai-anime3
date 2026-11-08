/* Hồi quy ForgeClient, đặc biệt lỗi GET /internal/progress -> HTTP 405.
 * Chạy không cần dependency: node mobile/tests/test_api.mjs
 */
import assert from 'node:assert/strict';
import { ForgeClient } from '../app/js/api.js';

let passed = 0;
function check(label, condition) {
  assert.ok(condition, label);
  passed += 1;
  console.log(`✔ ${label}`);
}

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  };
}

const idle = {
  progress: 0.4,
  eta_relative: 12,
  state: { sampling_step: 10, sampling_steps: 25, job_count: 1 },
  current_image: null,
};

// API chuẩn vẫn dùng GET và bỏ current_image để response nhẹ.
{
  const calls = [];
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return jsonResponse(idle);
    },
  });
  const info = await api.progress();
  check('tiến trình chuẩn dùng GET /sdapi/v1/progress', calls.length === 1
    && calls[0].init.method === 'GET'
    && new URL(calls[0].url).pathname === '/sdapi/v1/progress');
  check('tiến trình chuẩn gửi skip_current_image=true',
    new URL(calls[0].url).searchParams.get('skip_current_image') === 'true');
  check('dữ liệu tiến trình được chuẩn hoá', info.available
    && info.source === 'sdapi/v1/progress' && info.step === 10 && info.steps === 25);
}

// Mô phỏng đúng Forge: GET internal/progress trả 405, chỉ POST mới trả JSON.
{
  const calls = [];
  const api = new ForgeClient({
    base: 'https://forge.example/',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      const path = new URL(url).pathname;
      if (path === '/sdapi/v1/progress') return jsonResponse({ detail: 'Not Found' }, 404);
      if (path === '/internal/progress' && init.method !== 'POST') {
        return jsonResponse({ detail: 'Method Not Allowed' }, 405);
      }
      return jsonResponse(idle);
    },
  });
  const info = await api.progress();
  const internal = calls.find((call) => new URL(call.url).pathname === '/internal/progress');
  check('fallback /internal/progress dùng POST, không còn HTTP 405', info.available
    && info.source === 'internal/progress' && internal?.init.method === 'POST');
  check('POST internal/progress gửi JSON skip_current_image=true',
    internal?.init.headers['Content-Type'] === 'application/json'
    && JSON.parse(internal.init.body).skip_current_image === true);
}

// Chẩn đoán phải dùng đúng method cho cả 6 endpoint và nhận diện API/tiến trình.
{
  const calls = [];
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      const path = new URL(url).pathname;
      if (path === '/internal/progress' && init.method !== 'POST') {
        return jsonResponse({ detail: 'Method Not Allowed' }, 405);
      }
      if (path === '/sdapi/v1/options') {
        return jsonResponse({ sd_model_checkpoint: 'models/wai_v17.safetensors' });
      }
      if (path === '/sdapi/v1/sd-models') return jsonResponse([{ title: 'wai_v17' }]);
      if (path.endsWith('/progress')) return jsonResponse(idle);
      return jsonResponse({ api: true });
    },
  });
  const result = await api.diagnose();
  const internal = result.checks.find((item) => item.path === 'internal/progress');
  check('chẩn đoán kiểm tra đủ 6 endpoint', result.checks.length === 6 && calls.length === 6);
  check('chẩn đoán internal/progress dùng POST', internal.ok && internal.method === 'POST'
    && internal.status === 200);
  check('mọi endpoint đều OK khi Forge phản hồi đúng', result.checks.every((item) => item.ok)
    && result.hasApi && result.hasProgress && result.hasCompactApi && result.anyOk);
  check('chẩn đoán giữ method rõ ràng cho từng dòng UI', result.checks
    .filter((item) => item.path !== 'internal/progress')
    .every((item) => item.method === 'GET'));
}

// Endpoint nội bộ là dự phòng: nếu nó thiếu nhưng API chuẩn sống, tiến trình vẫn ổn.
{
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path === '/internal/progress') return jsonResponse({ detail: 'Not Found' }, 404);
      if (path.endsWith('/progress')) return jsonResponse(idle);
      if (path === '/sdapi/v1/sd-models') return jsonResponse([]);
      return jsonResponse({});
    },
  });
  const result = await api.diagnose();
  const internal = result.checks.find((item) => item.path === 'internal/progress');
  check('lỗi endpoint dự phòng không làm mất trạng thái tiến trình chính',
    result.hasProgress && !internal.ok && internal.optional && internal.status === 404);
}

// Response 200 nhưng body lớn bị đứt: lấy lại current_image, tuyệt đối không POST lại.
{
  let postCount = 0;
  let recoveryCalled = false;
  const progressCalls = [];
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const parsed = new URL(url);
      if (parsed.pathname === '/sdapi/v1/txt2img') {
        postCount += 1;
        return {
          ok: true,
          status: 200,
          text: async () => { throw new TypeError('body stream lost'); },
        };
      }
      if (parsed.pathname === '/sdapi/v1/progress') {
        progressCalls.push(parsed.searchParams.get('skip_current_image'));
        return jsonResponse({
          progress: 0.96,
          state: { sampling_step: 24, sampling_steps: 25, job_count: 1 },
          current_image: 'aGVsbG8=',
        });
      }
      return jsonResponse({}, 404);
    },
  });
  const result = await api.txt2img(
    { prompt: '1girl', negative_prompt: '', seed: 123, width: 1024, height: 1344 },
    { interval: 1, recoveryTimeout: 50, onRecover: () => { recoveryCalled = true; } },
  );
  check('đứt body ảnh được khôi phục từ current_image', result.recovered
    && result.images[0] === 'data:image/png;base64,aGVsbG8='
    && result.info.recovered_from_progress && result.info.seed === 123);
  check('khôi phục ảnh không POST tạo job lần hai', postCount === 1 && recoveryCalled);
  check('chỉ request current_image khi cần khôi phục', progressCalls.includes('false'));
}

// Preview đã đọc lúc >=90% vẫn dùng được nếu response lớn bị đứt ngay sau đó.
{
  let postCount = 0;
  let imageReads = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const parsed = new URL(url);
      if (parsed.pathname === '/sdapi/v1/txt2img') {
        postCount += 1;
        await new Promise((resolve) => setTimeout(resolve, 20));
        throw new TypeError('connection closed at final response');
      }
      if (parsed.pathname === '/vi-mobile/api/txt2img') return jsonResponse({}, 404);
      if (parsed.searchParams.get('skip_current_image') === 'false') imageReads += 1;
      return jsonResponse({
        progress: 0.96,
        state: { sampling_step: 24, sampling_steps: 25, job_count: 1 },
        current_image: 'cHJldmlldw==',
      });
    },
  });
  const result = await api.txt2img({ prompt: '1girl' }, { interval: 1, recoveryTimeout: 20 });
  check('dùng preview gần cuối đã cache khi response bị đứt', result.recovered
    && result.images[0] === 'data:image/png;base64,cHJldmlldw==');
  check('preview gần cuối chỉ được tải một lần và không tạo lại job', postCount === 1 && imageReads === 1);
}

// Không có bằng chứng job chạy thì không lấy ảnh cũ; lỗi phải nói đúng giai đoạn tải ảnh.
{
  let postCount = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path === '/sdapi/v1/txt2img') {
        postCount += 1;
        throw new TypeError('fetch failed');
      }
      if (path === '/vi-mobile/api/txt2img') return jsonResponse({}, 404);
      return jsonResponse({ progress: 0, state: { job_count: 0 }, current_image: 'anh-cu' });
    },
  });
  let failure = null;
  try {
    await api.txt2img({ prompt: '1girl' }, { interval: 1, recoveryTimeout: 1 });
  } catch (error) {
    failure = error;
  }
  check('không dùng ảnh cũ khi không xác nhận được job', failure?.status === 0
    && /tải ảnh kết quả/.test(failure.message) && /không tạo lại ngay/i.test(failure.message));
  check('request thất bại vẫn không tự tạo lại job', postCount === 1);
}

// WebView có thể trả text JSON đã cắt thay vì reject stream: vẫn phải đi nhánh khôi phục.
{
  let postCount = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const parsed = new URL(url);
      if (parsed.pathname === '/sdapi/v1/txt2img') {
        postCount += 1;
        return {
          ok: true,
          status: 200,
          text: async () => {
            await new Promise((resolve) => setTimeout(resolve, 30));
            return '{"images":["aGVsbG8=';
          },
        };
      }
      if (parsed.pathname === '/sdapi/v1/progress') {
        return jsonResponse({
          progress: 0,
          state: { sampling_step: 25, sampling_steps: 25, job_count: 0 },
          current_image: 'aGVsbG8=',
        });
      }
      return jsonResponse({}, 404);
    },
  });
  // Đã có tiến trình trước lúc response kết thúc để không nhận nhầm current_image cũ.
  let ticks = 0;
  const originalProgress = api.progress.bind(api);
  api.progress = async (...args) => {
    ticks += 1;
    if (ticks === 1) return { available: true, progress: 0.96, jobCount: 1 };
    return originalProgress(...args);
  };
  const result = await api.txt2img(
    { prompt: '1girl' },
    { interval: 20, recoveryTimeout: 50 },
  );
  check('JSON ảnh cắt giữa chừng vẫn được khôi phục', result.recovered
    && result.images[0] === 'data:image/png;base64,aGVsbG8=');
  check('JSON ảnh cắt không bị báo nhầm HTML và không POST lại', postCount === 1);
}

// Huỷ gần cuối phải thoát ngay, không chạy recovery hay trả preview sau thao tác Huỷ.
{
  const controller = new AbortController();
  let postCount = 0;
  let recoveryCalled = false;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      const parsed = new URL(url);
      if (parsed.pathname === '/vi-mobile/api/txt2img') return jsonResponse({}, 404);
      if (parsed.pathname === '/sdapi/v1/txt2img') {
        postCount += 1;
        return {
          ok: true,
          status: 200,
          text: () => new Promise((resolve, reject) => {
            const abort = () => reject(Object.assign(new Error('cancelled'), { name: 'AbortError' }));
            if (init.signal.aborted) abort();
            else init.signal.addEventListener('abort', abort, { once: true });
          }),
        };
      }
      return jsonResponse({
        progress: 0.96,
        state: { sampling_step: 24, sampling_steps: 25, job_count: 1 },
        current_image: 'cHJldmlldw==',
      });
    },
  });
  let failure = null;
  try {
    await api.txt2img({ prompt: '1girl' }, {
      signal: controller.signal,
      interval: 1,
      recoveryTimeout: 50,
      onProgress: () => controller.abort(),
      onRecover: () => { recoveryCalled = true; },
    });
  } catch (error) {
    failure = error;
  }
  check('Huỷ job được giữ là AbortError, không báo mất máy chủ', failure?.name === 'AbortError'
    && failure?.status === 0);
  check('Huỷ gần cuối không khôi phục ảnh và không tạo lại job', postCount === 1 && !recoveryCalled);
}

// Extension mới: dùng ảnh JPEG đã nén, không gọi thêm API chuẩn.
{
  const paths = [];
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      paths.push(path);
      if (path === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, txt2img_available: true, image_format: 'jpeg' });
      }
      if (path === '/vi-mobile/api/txt2img') {
        return jsonResponse({
          images: ['data:image/jpeg;base64,anBlZw=='],
          info: '{"seed": 42}',
          mobile_image_format: 'jpeg',
        });
      }
      if (path === '/sdapi/v1/txt2img') throw new Error('Không được gọi API chuẩn');
      return jsonResponse({}, 404);
    },
  });
  const result = await api.txt2img({ prompt: '1girl' }, { interval: 1 });
  check('app ưu tiên API ảnh nén và giữ đúng MIME JPEG', !result.recovered
    && result.images[0] === 'data:image/jpeg;base64,anBlZw==' && result.info.seed === 42);
  check('API ảnh nén thành công chỉ gửi một request tạo ảnh',
    paths.filter((path) => path.endsWith('txt2img')).length === 1);
}

// Extension cũ: health 404 thì chọn API chuẩn ngay, không POST thử route nén.
{
  const paths = [];
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      paths.push(path);
      if (path === '/vi-mobile/api/txt2img') return jsonResponse({ detail: 'Not Found' }, 404);
      if (path === '/sdapi/v1/txt2img') return jsonResponse({ images: ['cG5n'], info: '{}' });
      return jsonResponse({}, 404);
    },
  });
  const result = await api.txt2img({ prompt: '1girl' }, { interval: 1 });
  check('health 404 chọn API chuẩn trước khi tạo job', result.images.length === 1
    && paths.includes('/vi-mobile/api/health') && paths.includes('/sdapi/v1/txt2img')
    && !paths.includes('/vi-mobile/api/txt2img'));
}

// 500 có thể xảy ra sau khi job đã chạy: không được fallback rồi nhân đôi GPU/job.
{
  let standardPosts = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, txt2img_available: true, image_format: 'jpeg' });
      }
      if (path === '/vi-mobile/api/txt2img') return jsonResponse({ detail: 'CUDA error' }, 500);
      if (path === '/sdapi/v1/txt2img') {
        standardPosts += 1;
        return jsonResponse({ images: ['khong-duoc-goi'] });
      }
      return jsonResponse({}, 404);
    },
  });
  let failure = null;
  try {
    await api.txt2img({ prompt: '1girl' }, { interval: 1, recoveryTimeout: 1 });
  } catch (error) {
    failure = error;
  }
  check('lỗi 500 từ API nén không tự tạo lại job bằng API chuẩn',
    failure?.status === 500 && standardPosts === 0);
}

// Ngay cả 404 từ trong job cũng không được đổi endpoint và nhân đôi request.
{
  let standardPosts = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') return jsonResponse({ ok: true });
      if (path === '/vi-mobile/api/txt2img') return jsonResponse({ detail: 'Job error' }, 404);
      if (path === '/sdapi/v1/txt2img') {
        standardPosts += 1;
        return jsonResponse({ images: ['khong-duoc-goi'] });
      }
      return jsonResponse({}, 404);
    },
  });
  let failure = null;
  try {
    await api.txt2img({ prompt: '1girl' }, { interval: 1, recoveryTimeout: 1 });
  } catch (error) {
    failure = error;
  }
  check('404 sau POST nén cũng không tạo lại job bằng API chuẩn',
    failure?.status === 404 && standardPosts === 0);
}

console.log(`\n✅ ${passed} kiểm tra ForgeClient đạt.`);
