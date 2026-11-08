/* Hồi quy logic app điện thoại — Node stdlib, không DOM, không mạng, không GPU.
 *
 *   node mobile/tests/test_core.mjs
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as core from '../app/js/core.js';
import { TagData } from '../app/js/data.js';

const HERE = dirname(fileURLToPath(import.meta.url));
let passed = 0;
const failures = [];

function check(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`✔ ${name}`);
  } catch (error) {
    failures.push({ name, error });
    console.log(`✘ ${name}\n    ${error.message}`);
  }
}

// ------------------------------------------------------------------ chuẩn hoá
check('normKey bỏ dấu và dấu gạch dưới', () => {
  assert.equal(core.normKey('  Tóc_Dài  '), 'toc dai');
  assert.equal(core.normKey('ÁO DÀI'), 'ao dai');
  assert.equal(core.normKey('đôi mắt'), 'doi mat');
});

check('parseTags giữ trọng số và không nhầm 16:9', () => {
  const pieces = core.parseTags('1girl, (blue_eyes:1.2), ao dai:1.1, 16:9, <lora:x:0.8>');
  assert.deepEqual(pieces.map((p) => p.tag),
    ['1girl', 'blue_eyes', 'ao dai', '16:9', '<lora:x:0.8>']);
  assert.equal(pieces[1].weight, 1.2);
  assert.equal(pieces[2].weight, 1.1);
  assert.equal(pieces[3].weight, null, '16:9 là tỉ lệ, không phải trọng số');
  assert.equal(pieces[4].special, true);
});

check('parseTags bỏ trọng số vô lý', () => {
  const pieces = core.parseTags('tag:99, tag2:0.5');
  assert.equal(pieces[0].tag, 'tag:99');
  assert.equal(pieces[0].weight, null);
  assert.equal(pieces[1].weight, 0.5);
});

check('renderTag chỉ thêm ngoặc khi có trọng số khác 1', () => {
  assert.equal(core.renderTag('long_hair'), 'long_hair');
  assert.equal(core.renderTag('long_hair', 1.2), '(long_hair:1.2)');
  assert.equal(core.renderTag('long_hair', 1), 'long_hair');
});

check('splitPieces không cắt dấu phẩy trong ngoặc/LoRA', () => {
  const pieces = core.splitPieces('a, (b, c:1.2), <lora:x,1:0.5>, d');
  assert.deepEqual(pieces.map((p) => p.trim()), ['a', '(b, c:1.2)', '<lora:x,1:0.5>', 'd']);
});

// ------------------------------------------------------------------ dựng prompt
const fakeGroups = {
  masterpiece: 0, 'best quality': 0, rating_general: 1, '1girl': 3,
  long_hair: 8, 'blue eyes': 8, ao_dai: 9, smile: 10, sitting: 11, cityscape: 15,
};
const groupOf = (tag) => (fakeGroups[tag] ?? core.OTHER_GROUP);

check('normalisePrompt xếp theo nhóm, thêm chất lượng, khử trùng', () => {
  const out = core.normalisePrompt(
    'smile, long_hair, 1girl, smile, ao_dai, cityscape, sitting',
    { quality: 'masterpiece, best quality', ratingPositive: ['rating_general'], groupOf },
  );
  assert.equal(out,
    'masterpiece, best quality, rating_general, 1girl, long_hair, ao_dai, smile, sitting, cityscape');
});

check('normalisePrompt không nhân đôi tag chất lượng người dùng đã gõ', () => {
  const out = core.normalisePrompt('masterpiece, 1girl', { quality: 'masterpiece, best quality', groupOf });
  assert.equal(out, 'best quality, masterpiece, 1girl');
});

check('normalisePrompt giữ <lora:...> ở cuối', () => {
  const out = core.normalisePrompt('1girl, <lora:style:0.7>', { quality: '', groupOf });
  assert.equal(out, '1girl, <lora:style:0.7>');
});

check('dedupePieces bỏ tag con khi đã có tag ghép', () => {
  const pieces = core.dedupePieces(core.parseTags('blue eyes, eyes, long hair, hair'));
  assert.deepEqual(pieces.map((p) => p.tag), ['blue eyes', 'long hair']);
});

check('buildNegative gộp preset + phân loại, không lặp', () => {
  const out = core.buildNegative({
    preset: 'bad quality, worst quality, sketch',
    ratingNegative: ['rating_explicit', 'explicit', 'bad quality'],
    extra: 'watermark, sketch',
  });
  assert.equal(out, 'bad quality, worst quality, sketch, rating_explicit, explicit, watermark');
});

// ------------------------------------------------------------------ token
check('estimateTokens đếm gần đúng và chia mức ngân sách', () => {
  assert.equal(core.estimateTokens('1girl, solo'), 4);       // 1+1 token + 2 dấu phẩy? (mỗi mảnh 1)
  const many = Array.from({ length: 40 }, (_, i) => `tag${i}`).join(', ');
  const tokens = core.estimateTokens(many);
  assert.ok(tokens > 75, `40 tag phải vượt 1 cửa sổ, nhận ${tokens}`);
  assert.equal(core.tokenAdvice(50).level, 'ok');
  assert.equal(core.tokenAdvice(120).level, 'warn');
  assert.equal(core.tokenAdvice(400).level, 'bad');
});

// ------------------------------------------------------------------ payload
const DEFAULTS = {
  steps: 25, cfg_scale: 6, sampler_name: 'Euler a', scheduler: '', clip_skip: 2,
  width: 1024, height: 1344, seed: -1, batch_size: 1, enable_hr: true,
  hr_upscaler: 'RealESRGAN_x4plus_anime_6B', hr_scale: 1.5,
  hr_second_pass_steps: 20, denoising_strength: 0.4,
};

check('buildPayload giống PromptBuilder.payload (clip_skip -> override_settings)', () => {
  const body = core.buildPayload({
    positive: 'a, b', negative: 'c', defaults: DEFAULTS, overrides: { steps: 30, seed: 42 },
  });
  assert.equal(body.prompt, 'a, b');
  assert.equal(body.negative_prompt, 'c');
  assert.equal(body.steps, 30);
  assert.equal(body.seed, 42);
  assert.equal(body.clip_skip, undefined, 'clip_skip không gửi trực tiếp');
  assert.equal(body.override_settings.clip_stop_at_last_layers, 2);
  assert.equal(body.override_settings_restore_afterwards, true);
  assert.equal(body.scheduler, 'Automatic');
});

check('buildPayload đổi sampler Karras sang sampler + scheduler của Neo', () => {
  const body = core.buildPayload({
    positive: 'x', negative: '', defaults: DEFAULTS,
    overrides: { sampler_name: 'DPM++ 2M Karras' },
  });
  assert.equal(body.sampler_name, 'DPM++ 2M');
  assert.equal(body.scheduler, 'Karras');
});

check('buildPayload bỏ tham số hires khi tắt hires', () => {
  const body = core.buildPayload({ positive: 'x', negative: '', defaults: DEFAULTS, overrides: { enable_hr: false } });
  assert.equal(body.enable_hr, false);
  for (const key of ['hr_upscaler', 'hr_scale', 'hr_second_pass_steps', 'denoising_strength']) {
    assert.equal(body[key], undefined, `${key} phải bị bỏ`);
  }
});

check('buildPayload không nhận giá trị rỗng từ form', () => {
  const body = core.buildPayload({
    positive: 'x', negative: '', defaults: DEFAULTS, overrides: { steps: '', cfg_scale: null },
  });
  assert.equal(body.steps, 25);
  assert.equal(body.cfg_scale, 6);
});

check('payloadWarnings cảnh báo kích thước/CFG/Hires', () => {
  const warnings = core.payloadWarnings({ width: 1024, height: 2000, cfg_scale: 12, steps: 50, enable_hr: true, hr_scale: 2.5, batch_size: 4 });
  assert.ok(warnings.length >= 4, warnings.join(' | '));
  assert.equal(core.payloadWarnings({ ...DEFAULTS }).length, 0);
});

// ------------------------------------------------------------------ URL & lỗi
check('normalizeBaseUrl thêm https, bỏ / cuối', () => {
  assert.equal(core.normalizeBaseUrl('  abc.gradio.live/  '), 'https://abc.gradio.live');
  assert.equal(core.normalizeBaseUrl('http://192.168.1.5:7860/'), 'http://192.168.1.5:7860');
  assert.equal(core.normalizeBaseUrl(''), '');
});

check('apiUrl dùng đường dẫn tuyệt đối khi không có base', () => {
  assert.equal(core.apiUrl('', '/sdapi/v1/txt2img'), '/sdapi/v1/txt2img');
  assert.equal(core.apiUrl('', 'sdapi/v1/txt2img'), '/sdapi/v1/txt2img');
  assert.equal(core.apiUrl('https://x.gradio.live/', 'sdapi/v1/options'),
    'https://x.gradio.live/sdapi/v1/options');
});

check('explainError dịch lỗi thành việc cần làm', () => {
  assert.match(core.explainError(0), /link tunnel|CORS/i);
  assert.match(core.explainError(404), /--api/);
  assert.match(core.explainError(401), /đăng nhập/);
  assert.match(core.explainError(500), /VRAM/);
});

check('progressText đọc được cả tiến trình chuẩn hoá', () => {
  assert.equal(core.progressText({ available: true, progress: 0.4, step: 10, steps: 25, eta: 80 }, 30),
    '⏳ 30s · 40% · bước 10/25 · còn ~1m 20s');
  assert.match(core.progressText(null, 20), /chưa đọc được tiến trình/);
  assert.equal(core.formatDuration(75), '1m 15s');
});

check('seedFromInfo đọc cả seed và all_seeds', () => {
  assert.equal(core.seedFromInfo({ seed: 7 }), 7);
  assert.equal(core.seedFromInfo(JSON.stringify({ all_seeds: [9] })), 9);
  assert.equal(core.seedFromInfo({}), null);
});

// ------------------------------------------------------------------ dữ liệu thật
const payload = JSON.parse(readFileSync(join(HERE, '..', 'app', 'data', 'tags.json'), 'utf8'));
const data = new TagData(payload);

check('dữ liệu tag: đủ lớn và có bản dịch', () => {
  assert.ok(payload.tags.length > 50000, `chỉ có ${payload.tags.length} tag`);
  const translated = payload.tags.filter((row) => row[4]).length;
  assert.ok(translated > 20000, `chỉ có ${translated} tag có nghĩa tiếng Việt`);
  assert.equal(payload.styles.length, 506);
});

check('tra tiếng Việt ra tag tiếng Anh', () => {
  const top = data.search('toc dai', { limit: 5 }).map((row) => row.tag);
  assert.ok(top.includes('long_hair'), `nhận ${top.join(', ')}`);
  const aoDai = data.search('áo dài', { limit: 5 }).map((row) => row.tag);
  assert.ok(aoDai.length > 0);
});

check('tra tiếng Anh khớp chính xác đứng đầu', () => {
  const rows = data.search('1girl', { limit: 5 });
  assert.equal(rows[0].tag, '1girl');
  assert.ok(rows[0].count > 1000000);
});

check('lọc theo nhóm vẫn trả kết quả đúng nhóm', () => {
  const groupIndex = payload.groups.indexOf('background');
  const rows = data.search('', { limit: 10, group: groupIndex });
  assert.ok(rows.length > 0);
  assert.ok(rows.every((row) => row.group === groupIndex));
});

check('groupIndexOf và viOf dùng được cho tag phổ biến', () => {
  assert.equal(data.groupIndexOf('long_hair'), payload.groups.indexOf('appearance'));
  assert.equal(data.viOf('long_hair').length > 0, true);
  assert.equal(data.groupIndexOf('tag_khong_ton_tai_xyz'), core.OTHER_GROUP);
});

check('tìm phong cách vẽ theo tiếng Việt', () => {
  const rows = data.searchStyles('màu nước', { limit: 10 });
  assert.ok(rows.some((row) => row.tag.includes('watercolor')), rows.map((r) => r.tag).join(','));
});

check('presets sinh từ system_tags có đủ mục app cần', () => {
  for (const key of ['quality', 'negative', 'ratings', 'sizes', 'defaults', 'samplers', 'style_presets']) {
    assert.ok(payload.presets[key], `thiếu presets.${key}`);
  }
  assert.equal(payload.presets.ratings.length, 4);
  assert.ok(payload.presets.style_presets.length >= 12);
});

// ------------------------------------------------------------------ tổng kết
console.log(`\n${passed} kiểm tra đạt, ${failures.length} lỗi.`);
if (failures.length) {
  for (const failure of failures) console.error(`\n${failure.name}\n${failure.error.stack}`);
  process.exit(1);
}
