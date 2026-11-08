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
  globalThis.fetch = (input, init) => {
    const url = new URL(String(input), BASE).href;
    fetchCalls.push(url);
    return realFetch(url, init);
  };

  for (const key of ['window', 'document', 'HTMLElement', 'Node', 'Event', 'FormData',
    'File', 'Blob', 'navigator', 'location', 'localStorage', 'confirm']) {
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
    throw new Error(`quá thời gian chờ ${label}`);
  }

  const doc = window.document;
  const $ = (selector) => doc.querySelector(selector);
  const $$ = (selector) => Array.from(doc.querySelectorAll(selector));

  await import(join(APP, 'js', 'ui.js'));
  await until(() => !$('#splash'), { label: 'splash biến mất' });
  assert.ok($$('#sizeChips .chip').length >= 5, 'thiếu chip kích thước');
  assert.equal($$('#ratingChips .chip').length, 4, 'thiếu chip phân loại');

  // --- sinh ảnh qua Forge giả
  const prompt = $('#prompt');
  prompt.value = '1girl, solo, long_hair, ao dai, smile';
  prompt.dispatchEvent(new window.Event('input', { bubbles: true }));
  assert.match($('#tokenInfo').textContent, /\d+ tag/);

  $('#generateBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => /\d+%|Xong/.test($('#status').textContent), { label: 'tiến trình' });
  assert.ok(!$('#cancelBtn').classList.contains('hidden'), 'nút Huỷ phải hiện khi đang chạy');
  await until(() => $$('#resultImages img').length > 0, { timeout: 40000, label: 'ảnh trả về' });
  assert.match($('#status').textContent, /Xong/);
  assert.equal(fetchCalls.filter((url) => url.includes('txt2img')).length, 1,
    'mỗi lần bấm chỉ được POST txt2img một lần');

  // --- thư viện: ảnh vừa tạo phải xuất hiện trong tab Thư viện
  $('.tab-btn[data-tab="gallery"]').dispatchEvent(new window.Event('click', { bubbles: true }));
  await until(() => $$('#gallery button').length > 0, { label: 'ảnh vào thư viện' });
  assert.ok($('#galleryEmpty').classList.contains('hidden'),
    'thư viện còn trống dù vừa tạo ảnh');

  // --- kho tag tiếng Việt
  $('.tab-btn[data-tab="tags"]').dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(200);
  assert.ok($$('#tagFilters .chip').length > 10, 'thiếu chip nhóm tag');
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

  console.log('✅ smoke test UI: khởi động · sinh ảnh · tra tag · chèn tag · phong cách · cài đặt');
}

// Không dùng `finally` + process.exit: exit() thoát ngay, bỏ lại server giả chiếm cổng.
let exitCode = 0;
try {
  await main();
} catch (error) {
  console.error('❌ smoke test UI lỗi:', error.message);
  exitCode = 1;
}
server.kill('SIGTERM');
await new Promise((resolve) => setTimeout(resolve, 200));
process.exit(exitCode);
