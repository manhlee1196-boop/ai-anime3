/* Smoke test giao diện: chạy thật js/ui.js trên DOM giả (jsdom) + Forge giả.
 *
 *   npm i jsdom            # một lần, chỉ để test (app không cần jsdom)
 *   node mobile/tests/test_ui_smoke.mjs
 *
 * Kiểm tra: app khởi động, nạp kho tag, dựng chip, gọi /sdapi/v1/txt2img tới Forge
 * giả (qua mobile/serve.py --mock), đọc tiến trình, hiện ảnh, tra tag tiếng Việt,
 * chèn tag vào prompt, mở sheet phong cách/cài đặt. Không cần GPU.
 */
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..', 'app');
const ROOT = join(HERE, '..', '..');
const PORT = 8788;
const BASE = `http://127.0.0.1:${PORT}/`;

let JSDOM;
try {
  ({ JSDOM } = await import('jsdom'));
} catch (error) {
  console.log('⚠️  Bỏ qua smoke test UI: chưa có jsdom (npm i jsdom để chạy).');
  process.exit(0);
}

if (!fs.existsSync(join(APP, 'data', 'tags.json'))) {
  console.log('⚠️  Bỏ qua smoke test UI: chưa có mobile/app/data/tags.json '
    + '(chạy python3 mobile/build_data.py).');
  process.exit(0);
}

const server = spawn('python3', [join(ROOT, 'mobile', 'serve.py'), '--mock',
  '--port', String(PORT), '--host', '127.0.0.1'], { stdio: ['ignore', 'pipe', 'pipe'] });
const serverLog = [];
server.stdout.on('data', (chunk) => serverLog.push(String(chunk)));
server.stderr.on('data', (chunk) => serverLog.push(String(chunk)));

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForServer() {
  for (let i = 0; i < 60; i += 1) {
    try {
      const response = await fetch(`${BASE}sdapi/v1/options`);
      if (response.ok) return;
    } catch (error) {
      // chưa lên, thử lại
    }
    await wait(200);
  }
  throw new Error(`server không lên được:\n${serverLog.join('')}`);
}

async function main() {
  await waitForServer();

  const html = fs.readFileSync(join(APP, 'index.html'), 'utf8');
  const dom = new JSDOM(html, { url: BASE, pretendToBeVisual: true });
  const { window } = dom;

  const realFetch = globalThis.fetch;
  const fetchCalls = [];
  const generationPayloads = [];
  globalThis.fetch = (input, init) => {
    const url = new URL(String(input), BASE).href;
    fetchCalls.push(url);
    if (url.endsWith('/vi-mobile/api/jobs') && init?.body) {
      generationPayloads.push(JSON.parse(init.body).payload);
    }
    return realFetch(url, init);
  };

  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'FormData',
    'navigator', 'location', 'localStorage', 'confirm']) {
    const value = window[key] ?? globalThis[key];
    Object.defineProperty(globalThis, key, { value, writable: true, configurable: true });
  }
  window.scrollTo = () => {};
  window.Element.prototype.scrollIntoView = () => {};
  window.confirm = () => true;
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });

  async function until(fn, { timeout = 20000, label = 'điều kiện' } = {}) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      if (await fn()) return;
      await wait(100);
    }
    throw new Error(`quá thời gian chờ ${label}; status=${doc.querySelector('#status')?.textContent}`);
  }

  const doc = window.document;
const state_settings_api_url = () => {
  try {
    return JSON.parse(window.localStorage.getItem('anime3.mobile.settings.v1') || '{}').apiUrl || '';
  } catch (error) {
    return '';
  }
};
  const $ = (selector) => doc.querySelector(selector);
  const $$ = (selector) => Array.from(doc.querySelectorAll(selector));

  await import(join(APP, 'js', 'ui.js'));
  await until(() => !$('#splash'), { label: 'splash biến mất' });
  assert.ok($$('#sizeChips .chip').length >= 5, 'thiếu chip kích thước');
  assert.equal($$('#ratingChips .chip').length, 4, 'thiếu chip phân loại');
  assert.ok($$('#quickTagList .quick-tag').length >= 5, 'thiếu gợi ý tag nhanh trong prompt');

  // --- gợi ý trực tiếp trong prompt: gõ tiếng Việt, chọn tag Anh từ kho offline
  const prompt = $('#prompt');
  prompt.value = '1girl, toc dai';
  prompt.setSelectionRange(prompt.value.length, prompt.value.length);
  prompt.dispatchEvent(new window.Event('input', { bubbles: true }));
  await until(() => $$('#tagSuggestList .suggestion-row')
    .some((row) => row.textContent.includes('long_hair')), { label: 'gợi ý tag trong prompt' });

  // Enter khi IME đang ghép dấu phải được giữ cho bàn phím, không chọn gợi ý.
  const imeEnter = new window.KeyboardEvent('keydown', {
    key: 'Enter', isComposing: true, bubbles: true, cancelable: true,
  });
  prompt.dispatchEvent(imeEnter);
  assert.equal(prompt.value, '1girl, toc dai');
  assert.equal(imeEnter.defaultPrevented, false);

  // Trong lúc composition, app giữ nguyên Unicode và chỉ gợi ý sau compositionend.
  prompt.dispatchEvent(new window.Event('compositionstart', { bubbles: true }));
  prompt.value = '1girl, tóc dài';
  prompt.setSelectionRange(prompt.value.length, prompt.value.length);
  const composingInput = new window.Event('input', { bubbles: true });
  Object.defineProperty(composingInput, 'isComposing', { value: true });
  prompt.dispatchEvent(composingInput);
  await wait(200);
  assert.equal(prompt.value, '1girl, tóc dài');
  assert.ok($('#tagSuggest').classList.contains('hidden'));
  prompt.dispatchEvent(new window.Event('compositionend', { bubbles: true }));
  await until(() => $$('#tagSuggestList .suggestion-row')
    .some((row) => row.textContent.includes('long_hair')), { label: 'gợi ý sau khi ghép dấu' });

  $$('#tagSuggestList .suggestion-row').find((row) => row.textContent.includes('long_hair'))
    .dispatchEvent(new window.Event('click', { bubbles: true }));
  assert.match(prompt.value, /1girl, long_hair, $/);
  assert.ok($('#tagSuggest').classList.contains('hidden'), 'gợi ý không đóng sau khi chọn');

  // --- sinh ảnh qua Forge giả: prompt Việt đã biết phải được gửi thành tag Anh
  prompt.value = '1girl, solo, tóc dài, áo dài, nụ cười';
  prompt.dispatchEvent(new window.Event('input', { bubbles: true }));
  assert.match($('#tokenInfo').textContent, /\d+ tag/);

  $('#generateBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => /\d+%|Xong/.test($('#status').textContent), { label: 'tiến trình' });
  assert.ok(!$('#cancelBtn').classList.contains('hidden'), 'nút Huỷ phải hiện khi đang chạy');
  await until(() => $$('#resultImages img').length > 0, {
    timeout: 40000,
    label: `ảnh trả về; status=${$('#status').textContent}; calls=${fetchCalls.join(', ')}`,
  });
  assert.match($('#status').textContent, /xong/i);
  assert.equal(fetchCalls.filter((url) => url.endsWith('/vi-mobile/api/jobs')).length, 1,
    'mỗi lần bấm chỉ được POST job một lần');
  assert.equal(fetchCalls.filter((url) => url.includes('/sdapi/v1/txt2img')).length, 0,
    'không được gọi API base64 đồng bộ');
  assert.ok(fetchCalls.some((url) => url.includes('/vi-mobile/api/files/')),
    'phải tải file binary từ manifest');
  assert.ok($('#resultImages img').src.startsWith('blob:'),
    'ảnh kết quả phải hiển thị bằng Object URL, không phải data URL');
  assert.equal(generationPayloads.length, 1);
  assert.match(generationPayloads[0].prompt, /long_hair/);
  assert.match(generationPayloads[0].prompt, /ao_dai/);
  assert.match(generationPayloads[0].prompt, /smile/);
  assert.doesNotMatch(generationPayloads[0].prompt, /tóc dài|áo dài|nụ cười/);

  // --- thư viện: ảnh vừa tạo phải xuất hiện trong tab Thư viện
  $('.tab-btn[data-tab="gallery"]').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => $$('#gallery button').length > 0, { label: 'ảnh vào thư viện' });
  assert.ok($('#galleryEmpty').classList.contains('hidden'),
    'thư viện còn trống dù vừa tạo ảnh');
  $('#gallery button').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => !$('#sheetImage').classList.contains('hidden'), { label: 'mở Blob từ thư viện' });
  assert.ok($('#imageView').src.startsWith('blob:'), 'ảnh lưu phải đọc lại bằng Object URL');
  $('#sheetImage [data-close]').dispatchEvent(new window.Event('click', { bubbles: true }));

  // --- kho tag tiếng Việt
  $('.tab-btn[data-tab="tags"]').dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(200);
  assert.ok($$('#tagFilters .chip').length > 10, 'thiếu chip nhóm tag');
  assert.match($('#tagDataMeta').textContent, /95\.939 tag/);

  // Lỗi cũ: key nhóm dạng chuỗi bị so với index dạng số nên mọi nhóm đều rỗng.
  $('#tagFilters [data-group="background"]').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => $$('#tagResults .tag-row').length > 0, { label: 'tag nhóm bối cảnh' });
  assert.ok($$('#tagResults .tag-row').some((row) => row.textContent.includes('simple_background')));
  assert.match($('#tagResultMeta').textContent, /Bối cảnh/);
  $('#tagFilters .chip').dispatchEvent(new window.Event('click', { bubbles: true }));

  const search = $('#tagSearch');
  search.value = 'toc dai';
  search.dispatchEvent(new window.Event('input', { bubbles: true }));
  await until(() => $$('#tagResults .tag-row').some((row) => row.textContent.includes('long_hair')),
    { label: 'kết quả tìm tag' });
  const row = $$('#tagResults .tag-row').find((item) => item.textContent.includes('long_hair'));
  row.dispatchEvent(new window.Event('click', { bubbles: true }));
  assert.ok(!$('#tagSelBar').classList.contains('hidden'), 'thanh chọn tag phải hiện');
  prompt.value = '1girl';
  $('#tagInsertBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  assert.ok(prompt.value.includes('long_hair'), 'tag chưa được chèn vào prompt');

  // --- phong cách + cài đặt
  $('#styleBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  assert.ok(!$('#sheetStyle').classList.contains('hidden'), 'sheet phong cách không mở');
  assert.ok($$('#stylePresets .chip').length >= 12, 'thiếu 12 công thức phong cách');
  assert.ok($$('#styleList .tag-row').length > 0, 'danh sách 506 tag phong cách rỗng');
  $('#sheetStyle [data-close]').dispatchEvent(new window.Event('click', { bubbles: true }));

  $('#settingsBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  assert.ok($$('#setQuality option').length >= 4, 'thiếu preset chất lượng');
  assert.ok($$('#setSampler option').length >= 6, 'thiếu danh sách sampler');

  // --- tab Máy chủ: mở Colab, dán link, tự nhận link, chẩn đoán
  $('.tab-btn[data-tab="server"]').dispatchEvent(new window.Event('click', { bubbles: true }));
  assert.ok($('#tab-server').classList.contains('active'), 'tab Máy chủ không mở');
  assert.ok($('#serverState').textContent.length > 0, 'thiếu nhãn trạng thái máy chủ');

  // nút "Mở Colab & chạy" phải mở đúng notebook (không phải link Github/Colab chung)
  const opened = [];
  window.open = (url) => { opened.push(url); return {}; };
  $('#openColabBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => opened.length === 1, { label: 'mở Colab' });
  assert.match(opened[0],
    /^https:\/\/colab\.research\.google\.com\/github\/[^/]+\/[^/]+\/blob\/.+WAI_v17_1click\.ipynb$/);

  // clipboard giả + Forge giả cho host tunnel (khỏi gọi mạng thật)
  const clipboard = { text: '', writes: [] };
  Object.defineProperty(window.navigator, 'clipboard', {
    configurable: true,
    value: {
      readText: async () => clipboard.text,
      writeText: async (text) => { clipboard.writes.push(text); },
    },
  });
  const jsonResponse = (body, status = 200) => new Response(JSON.stringify(body),
    { status, headers: { 'content-type': 'application/json' } });
  const realGlobalFetch = globalThis.fetch;
  globalThis.fetch = (input, init) => {
    const url = new URL(String(input), BASE);
    if (url.hostname === 'abc123.gradio.live') {
      if (url.pathname.endsWith('/sdapi/v1/options')) {
        return Promise.resolve(jsonResponse({ sd_model_checkpoint: 'wai_v17_abc.safetensors' }));
      }
      // Forge thật chỉ nhận POST ở route nội bộ; GET phải bị mô phỏng là 405.
      if (url.pathname.endsWith('/internal/progress') && init?.method !== 'POST') {
        return Promise.resolve(jsonResponse({ detail: 'Method Not Allowed' }, 405));
      }
      if (url.pathname.includes('progress')) {
        return Promise.resolve(jsonResponse({ progress: 0, state: {}, current_image: null }));
      }
      return Promise.resolve(jsonResponse({}));
    }
    if (url.hostname === '192.168.1.9') {
      return Promise.resolve(jsonResponse({ detail: 'unreachable' }, 502));
    }
    return realGlobalFetch(input, init);
  };

  // dán link Forge đã chết: phải lưu địa chỉ + báo "không kết nối được"
  clipboard.text = 'Link public: http://192.168.1.9:7860';
  $('#pasteLinkBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => state_settings_api_url() === 'http://192.168.1.9:7860',
    { label: 'lưu địa chỉ Forge từ clipboard' });
  await until(() => $('#serverState').textContent === 'không kết nối được',
    { label: 'báo link chết' });
  assert.ok($$('#linkList .tag-row').length >= 1, 'lịch sử link trống');

  // quay lại app sau khi chạy Colab: tự đọc clipboard, thấy link sống -> kết nối
  clipboard.text = 'Link public: https://abc123.gradio.live';
  document.dispatchEvent(new window.Event('visibilitychange'));
  await until(() => state_settings_api_url() === 'https://abc123.gradio.live',
    { timeout: 15000, label: 'tự nhận link khi quay lại app' });
  await until(() => $('#serverState').textContent === 'đã kết nối', { label: 'ping link mới' });
  assert.match($('#serverModel').textContent, /wai_v17_abc/,
    'không hiện tên model sau khi tự kết nối');
  assert.ok($$('#linkList .tag-row').length >= 2, 'lịch sử link không ghi thêm link mới');

  // copy lệnh lấy link mới cho Colab
  $('#copyRestartCmdBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => clipboard.writes.some((text) => text.includes('--restart')),
    { label: 'copy lệnh lấy link mới' });

  // chẩn đoán: đủ 6 endpoint, internal/progress phải POST và có job API
  $('#diagnoseBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => $$('#diagnoseOut .diag-line').length === 6, { label: 'kết quả chẩn đoán' });
  assert.equal($$('#diagnoseOut .diag-line.ok').length, 6, 'chẩn đoán có endpoint lỗi');
  assert.match($('#diagnoseOut').textContent, /POST \/internal\/progress/);
  assert.doesNotMatch($('#diagnoseOut').textContent, /HTTP 405/);
  assert.match($('#diagnoseOut .diag-summary').textContent, /Kết nối ổn/);
  assert.equal($('#diagnoseBtn').disabled, false, 'nút chẩn đoán không được mở lại');

  globalThis.fetch = realGlobalFetch;

  console.log('✅ smoke test UI: khởi động · sinh ảnh · tra tag · chèn tag · phong cách · cài đặt'
    + ' · Máy chủ (Colab, dán link, chẩn đoán)');
}

// Không dùng `finally` + process.exit: exit() thoát ngay, bỏ lại server giả chiếm cổng.
let exitCode = 0;
try {
  await main();
} catch (error) {
  console.error('❌ smoke test UI lỗi:', error.message);
  console.error(serverLog.slice(-30).join(''));
  exitCode = 1;
}
server.kill('SIGTERM');
await new Promise((resolve) => setTimeout(resolve, 200));
process.exit(exitCode);
