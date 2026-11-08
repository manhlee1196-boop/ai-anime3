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
      return jsonResponse({ api: true, async_jobs: true });
    },
  });
  const result = await api.diagnose();
  const internal = result.checks.find((item) => item.path === 'internal/progress');
  check('chẩn đoán kiểm tra đủ 6 endpoint', result.checks.length === 6 && calls.length === 6);
  check('chẩn đoán internal/progress dùng POST', internal.ok && internal.method === 'POST'
    && internal.status === 200);
  check('mọi endpoint đều OK khi Forge phản hồi đúng', result.checks.every((item) => item.ok)
    && result.hasApi && result.hasProgress && result.hasAsyncJobs && result.anyOk);
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

// Job nền: chỉ metadata nhỏ, ảnh tải từ signed URL thành Blob, không base64/job trùng.
{
  const JOB = 'a'.repeat(32);
  let createPosts = 0;
  let standardPosts = 0;
  let signedAuth = null;
  let submittedKey = '';
  let downloadProgress = null;
  const api = new ForgeClient({
    base: 'https://forge.example', user: 'user', pass: 'pass',
    fetchImpl: async (url, init) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, async_jobs: true, object_storage: { configured: true } });
      }
      if (path === '/vi-mobile/api/jobs' && init.method === 'POST') {
        createPosts += 1;
        submittedKey = JSON.parse(init.body).idempotency_key;
        return jsonResponse({ job_id: JOB, status: 'queued' }, 202);
      }
      if (path === `/vi-mobile/api/jobs/${JOB}/result`) {
        return jsonResponse({
          info: { seed: 42 },
          files: [{ name: '000.png', size: 4, mime: 'image/png', storage: 's3',
            url: 'https://cdn.example/signed/000.png' }],
        });
      }
      if (path === `/vi-mobile/api/jobs/${JOB}`) return jsonResponse({ job_id: JOB, status: 'done' });
      if (url === 'https://cdn.example/signed/000.png') {
        signedAuth = init.headers.Authorization || '';
        return {
          ok: true, status: 200,
          blob: async () => new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'image/png' }),
          text: async () => '',
        };
      }
      if (path === '/sdapi/v1/txt2img') standardPosts += 1;
      return jsonResponse({}, 404);
    },
  });
  const result = await api.txt2img({ prompt: '1girl' }, {
    interval: 1, idempotencyKey: 'same-request-42',
    onDownload: (progress) => { downloadProgress = progress; },
  });
  check('job nền trả Blob từ signed URL, giữ seed và tiến trình tải', result.jobId === JOB
    && result.info.seed === 42 && result.images[0] instanceof Blob
    && result.images[0].size === 4 && result.images[0].type === 'image/png'
    && downloadProgress?.loaded === 4);
  check('signed URL không nhận Basic Auth và không gọi API txt2img cũ', !signedAuth
    && standardPosts === 0 && createPosts === 1 && submittedKey === 'same-request-42');
}

// Lỗi đọc trạng thái được retry độc lập, tuyệt đối không POST job mới.
{
  const JOB = 'b'.repeat(32);
  let createPosts = 0;
  let statusReads = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') return jsonResponse({ ok: true, async_jobs: true });
      if (path === '/vi-mobile/api/jobs' && init.method === 'POST') {
        createPosts += 1;
        return jsonResponse({ job_id: JOB, status: 'queued' }, 202);
      }
      if (path === `/vi-mobile/api/jobs/${JOB}/result`) {
        return jsonResponse({ info: {}, files: [{ name: '000.png', size: 1,
          mime: 'image/png', url: 'https://cdn.example/one.png' }] });
      }
      if (path === `/vi-mobile/api/jobs/${JOB}`) {
        statusReads += 1;
        if (statusReads <= 2) throw new TypeError('temporary network failure');
        return jsonResponse({ job_id: JOB, status: 'done' });
      }
      if (url === 'https://cdn.example/one.png') {
        return { ok: true, status: 200, blob: async () => new Blob([new Uint8Array([9])]), text: async () => '' };
      }
      return jsonResponse({}, 404);
    },
  });
  const result = await api.txt2img({ prompt: '1girl' }, { interval: 1 });
  check('retry đọc trạng thái không tạo lại job', result.images.length === 1
    && createPosts === 1 && statusReads >= 3);
}

// Extension cũ/thiếu job API phải báo cập nhật, không âm thầm quay về base64.
{
  let posts = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      if (new URL(url).pathname === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, async_jobs: false });
      }
      if (init.method === 'POST') posts += 1;
      return jsonResponse({}, 404);
    },
  });
  let failure = null;
  try { await api.txt2img({ prompt: '1girl' }, { interval: 1 }); }
  catch (error) { failure = error; }
  check('thiếu async_jobs thì dừng trước khi tạo job, không fallback base64',
    failure?.status === 409 && /không dùng lại API base64/.test(failure.message) && posts === 0);
}

// Job lỗi: không tải manifest và không tạo job khác.
{
  const JOB = 'c'.repeat(32);
  let createPosts = 0;
  let resultReads = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') return jsonResponse({ ok: true, async_jobs: true });
      if (path === '/vi-mobile/api/jobs' && init.method === 'POST') {
        createPosts += 1;
        return jsonResponse({ job_id: JOB, status: 'queued' }, 202);
      }
      if (path === `/vi-mobile/api/jobs/${JOB}/result`) resultReads += 1;
      if (path === `/vi-mobile/api/jobs/${JOB}`) {
        return jsonResponse({ job_id: JOB, status: 'error', error: 'CUDA out of memory' });
      }
      return jsonResponse({}, 404);
    },
  });
  let failure = null;
  try { await api.txt2img({ prompt: '1girl' }, { interval: 1 }); }
  catch (error) { failure = error; }
  check('job lỗi được giữ nguyên, không đọc manifest hoặc POST lại', failure?.status === 500
    && /CUDA out of memory/.test(failure.message) && createPosts === 1 && resultReads === 0);
}

// Huỷ gọi DELETE đúng job_id.
{
  const JOB = 'd'.repeat(32);
  let call = null;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      call = { url, init };
      return jsonResponse({ job_id: JOB, status: 'cancelled' });
    },
  });
  const result = await api.cancelJob(JOB);
  check('huỷ job dùng DELETE đúng job_id', result.status === 'cancelled'
    && call.init.method === 'DELETE' && new URL(call.url).pathname === `/vi-mobile/api/jobs/${JOB}`);
}

// Tải local bị đứt sau 2 byte: lượt hai phải Range từ byte 2 và nối đúng dữ liệu.
{
  let fileCalls = 0;
  let range = '';
  let auth = '';
  const api = new ForgeClient({
    base: 'https://forge.example', user: 'user', pass: 'pass',
    fetchImpl: async (url, init) => {
      fileCalls += 1;
      range = init.headers.Range || '';
      auth = init.headers.Authorization || '';
      if (fileCalls === 1) {
        return {
          ok: true, status: 200,
          body: { getReader: () => {
            let sent = false;
            return { read: async () => {
              if (!sent) {
                sent = true;
                return { done: false, value: new Uint8Array([1, 2]) };
              }
              throw new TypeError('stream lost');
            } };
          } },
          text: async () => '', blob: async () => new Blob([]),
        };
      }
      return {
        ok: true, status: 206,
        blob: async () => new Blob([new Uint8Array([3, 4])], { type: 'image/png' }),
        text: async () => '',
      };
    },
  });
  const blob = await api.downloadFile({
    name: '000.png', size: 4, mime: 'image/png', url: '/vi-mobile/api/files/a/000.png',
  });
  const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()));
  check('resume Range nối đúng byte và giữ auth ở file local', fileCalls === 2
    && range === 'bytes=2-' && auth.startsWith('Basic ')
    && bytes.join(',') === '1,2,3,4' && blob.type === 'image/png');
}

// Upscale dùng cùng job nền nhưng operation riêng; ảnh kết quả vẫn tải bằng binary.
{
  const JOB = 'e'.repeat(32);
  let submitted = null;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, async_jobs: true, extras_available: true });
      }
      if (path === '/vi-mobile/api/jobs' && init.method === 'POST') {
        submitted = JSON.parse(init.body);
        return jsonResponse({ job_id: JOB, status: 'queued' }, 202);
      }
      if (path === `/vi-mobile/api/jobs/${JOB}/result`) {
        return jsonResponse({ info: { raw: 'upscaled' }, files: [{ name: '000.png', size: 1,
          mime: 'image/png', url: 'https://cdn.example/upscaled.png' }] });
      }
      if (path === `/vi-mobile/api/jobs/${JOB}`) return jsonResponse({ job_id: JOB, status: 'done' });
      if (url === 'https://cdn.example/upscaled.png') {
        return { ok: true, status: 200, blob: async () => new Blob([new Uint8Array([8])],
          { type: 'image/png' }), text: async () => '' };
      }
      return jsonResponse({}, 404);
    },
  });
  const result = await api.extras({ image: 'ZmFrZQ==', upscaling_resize: 2,
    upscaler_1: 'RealESRGAN_x4plus_anime_6B' }, { interval: 1 });
  check('extras gửi operation riêng và nhận Blob qua manifest', submitted.operation === 'extras'
    && submitted.payload.upscaling_resize === 2 && result.images[0] instanceof Blob
    && result.images[0].size === 1 && result.info.raw === 'upscaled');
}

// img2img dùng operation và capability riêng, vẫn nhận ảnh qua file binary.
{
  const JOB = 'f'.repeat(32);
  let submitted = null;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      const path = new URL(url).pathname;
      if (path === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, async_jobs: true, img2img_available: true });
      }
      if (path === '/vi-mobile/api/jobs' && init.method === 'POST') {
        submitted = JSON.parse(init.body);
        return jsonResponse({ job_id: JOB, status: 'queued' }, 202);
      }
      if (path === `/vi-mobile/api/jobs/${JOB}/result`) {
        return jsonResponse({ info: { seed: 43 }, files: [{ name: '000.png', size: 1,
          mime: 'image/png', url: 'https://cdn.example/img2img.png' }] });
      }
      if (path === `/vi-mobile/api/jobs/${JOB}`) return jsonResponse({ job_id: JOB, status: 'done' });
      if (url === 'https://cdn.example/img2img.png') {
        return { ok: true, status: 200, blob: async () => new Blob([new Uint8Array([7])],
          { type: 'image/png' }), text: async () => '' };
      }
      return jsonResponse({}, 404);
    },
  });
  const result = await api.img2img({ prompt: '1girl', init_images: ['ZmFrZQ=='],
    denoising_strength: 0.55, resize_mode: 1 }, { interval: 1 });
  check('img2img gửi operation riêng và tải Blob từ manifest', submitted.operation === 'img2img'
    && submitted.payload.denoising_strength === 0.55 && result.info.seed === 43
    && result.images[0] instanceof Blob && result.images[0].size === 1);
}

// Server cũ không có img2img_available: dừng trước POST thay vì gọi nhầm txt2img.
{
  let posts = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      if (new URL(url).pathname === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, async_jobs: true });
      }
      if (init.method === 'POST') posts += 1;
      return jsonResponse({}, 404);
    },
  });
  let failure = null;
  try { await api.img2img({ prompt: '1girl', init_images: ['ZmFrZQ=='] }, { interval: 1 }); }
  catch (error) { failure = error; }
  check('thiếu img2img job API thì dừng trước khi POST', failure?.status === 409
    && /img2img job API/.test(failure.message) && posts === 0);
}

// Server cũ không có extras_available: báo cập nhật, tuyệt đối không gửi job sai endpoint.
{
  let posts = 0;
  const api = new ForgeClient({
    base: 'https://forge.example',
    fetchImpl: async (url, init) => {
      if (new URL(url).pathname === '/vi-mobile/api/health') {
        return jsonResponse({ ok: true, async_jobs: true });
      }
      if (init.method === 'POST') posts += 1;
      return jsonResponse({}, 404);
    },
  });
  let failure = null;
  try { await api.extras({ image: 'ZmFrZQ==' }, { interval: 1 }); }
  catch (error) { failure = error; }
  check('thiếu extras job API thì dừng trước khi POST', failure?.status === 409
    && /Upscale job API/.test(failure.message) && posts === 0);
}

console.log(`\n✅ ${passed} kiểm tra ForgeClient đạt.`);
