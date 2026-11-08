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

// Chẩn đoán phải dùng đúng method cho cả 5 endpoint và nhận diện API/tiến trình.
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
  check('chẩn đoán kiểm tra đủ 5 endpoint', result.checks.length === 5 && calls.length === 5);
  check('chẩn đoán internal/progress dùng POST', internal.ok && internal.method === 'POST'
    && internal.status === 200);
  check('mọi endpoint đều OK khi Forge phản hồi đúng', result.checks.every((item) => item.ok)
    && result.hasApi && result.hasProgress && result.anyOk);
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

console.log(`\n✅ ${passed} kiểm tra ForgeClient đạt.`);
