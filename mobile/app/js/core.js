/**
 * Lõi logic thuần của app điện thoại: không DOM, không mạng — test được bằng Node.
 *
 * Mọi quy ước ở đây lấy từ chính prompt_lib của repo (Python), để app điện thoại
 * dựng prompt và gửi payload giống hệt app Gradio trên Colab:
 * - thứ tự nhóm: prompt_lib/groups.py (GROUP_ORDER)
 * - tag chất lượng / phân loại / negative / kích thước: prompt_lib/system_tags.py
 * - payload /sdapi/v1/txt2img: PromptBuilder.payload() trong prompt_lib/builder.py
 */

/** Thứ tự nhóm chuẩn Illustrious/WAI (prompt_lib/groups.py). */
export const GROUP_ORDER = [
  'quality', 'rating', 'source', 'subject', 'character', 'copyright', 'lore',
  'species', 'appearance', 'clothing', 'expression', 'pose', 'action',
  'sexual', 'object', 'background', 'camera', 'artist', 'meta', 'negative', 'other',
];

/** Nhóm mặc định khi dữ liệu không nói gì khác. */
export const OTHER_GROUP = GROUP_ORDER.length - 1;

/** Ghép chuỗi kiểu `(tag:1.2)` như prompt_lib/builder.py. */
export function renderTag(tag, weight) {
  if (weight === null || weight === undefined) return tag;
  const w = Number(weight);
  if (!Number.isFinite(w) || w === 1) return tag;
  return `(${tag}:${trimNumber(w)})`;
}

function trimNumber(value) {
  return String(Math.round(value * 1000) / 1000);
}

/** Bỏ dấu tiếng Việt: 'áo dài' -> 'ao dai'. */
export function unaccent(text) {
  const s = String(text ?? '');
  if (!/[^\x00-\x7F]/.test(s)) return s;
  return s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D');
}

/** Chuẩn hoá để so khớp: chữ thường, bỏ dấu, '_' -> khoảng trắng, gộp khoảng trắng. */
export function normKey(text) {
  return unaccent(String(text ?? '').trim().toLowerCase())
    .replace(/_/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .join(' ');
}

const LORA_RE = /^<(lora|lyco|embedding|hypernet):/i;
const WEIGHT_SUFFIX_RE = /^(.*?):(\d+(?:\.\d+)?)$/;

/**
 * Tách chuỗi prompt thành từng mảnh, giữ trọng số.
 * Chấp nhận `tag`, `tag:1.2`, `(tag:1.2)`, `<lora:x:0.8>`.
 * Không nhầm `16:9` với cú pháp trọng số (vì 9 không phải trọng số hợp lệ... trừ khi
 * người dùng thật sự muốn `16:9:1.2` — khi đó phần đuôi vẫn được hiểu đúng).
 */
export function parseTags(text) {
  const out = [];
  for (const raw of splitPieces(text)) {
    const piece = raw.trim();
    if (!piece) continue;
    if (LORA_RE.test(piece)) {
      out.push({ tag: piece, weight: null, special: true });
      continue;
    }
    let body = piece;
    let weight = null;
    // Bóc lớp ngoặc ngoài cùng: "(tag:1.2)"
    if (body.startsWith('(') && body.endsWith(')')) {
      const inner = body.slice(1, -1);
      const m = inner.match(WEIGHT_SUFFIX_RE);
      if (m && isWeight(m[2])) {
        body = m[1].trim();
        weight = Number(m[2]);
      } else {
        body = inner.trim();
      }
    } else {
      const m = body.match(WEIGHT_SUFFIX_RE);
      if (m && isWeight(m[2]) && /[a-z_]/i.test(m[1])) {
        body = m[1].trim();
        weight = Number(m[2]);
      }
    }
    if (!body) continue;
    out.push({ tag: body, weight });
  }
  return out;
}

function isWeight(text) {
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 && value <= 5;
}

/** Cắt theo dấu phẩy nhưng tôn trọng ngoặc và <lora:...> (giống split_prompt của Python). */
export function splitPieces(text) {
  const s = String(text ?? '');
  const out = [];
  let depth = 0;
  let angle = 0;
  let current = '';
  for (const ch of s) {
    if (ch === '<') angle += 1;
    else if (ch === '>' && angle > 0) angle -= 1;
    else if (!angle && ch === '(') depth += 1;
    else if (!angle && ch === ')' && depth > 0) depth -= 1;
    if (ch === ',' && depth === 0 && angle === 0) {
      out.push(current);
      current = '';
      continue;
    }
    current += ch;
  }
  out.push(current);
  return out;
}

/** Tag đang gõ tại con trỏ, bỏ qua dấu phẩy trong ngoặc và <lora:...>. */
export function activeTagFragment(text, caret = null) {
  const value = String(text ?? '');
  const requested = caret === null || caret === undefined ? value.length : Number(caret);
  const position = Math.max(0, Math.min(value.length, Number.isFinite(requested) ? requested : 0));
  let depth = 0;
  let angle = 0;
  let start = 0;
  for (let i = 0; i < position; i += 1) {
    const ch = value[i];
    if (ch === '<') angle += 1;
    else if (ch === '>' && angle > 0) angle -= 1;
    else if (!angle && ch === '(') depth += 1;
    else if (!angle && ch === ')' && depth > 0) depth -= 1;
    if (ch === ',' && depth === 0 && angle === 0) start = i + 1;
  }

  let end = position;
  for (; end < value.length; end += 1) {
    const ch = value[end];
    if (ch === ',' && depth === 0 && angle === 0) break;
    if (ch === '<') angle += 1;
    else if (ch === '>' && angle > 0) angle -= 1;
    else if (!angle && ch === '(') depth += 1;
    else if (!angle && ch === ')' && depth > 0) depth -= 1;
  }
  const leading = value.slice(start, position).match(/^\s*/)?.[0].length || 0;
  const from = start + leading;
  return { start: from, end, query: value.slice(from, position).trim() };
}

/** Thay tag đang gõ bằng gợi ý, giữ các tag phía sau và đưa con trỏ tới tag kế tiếp. */
export function replaceActiveTag(text, caret, tag) {
  const value = String(text ?? '');
  const replacement = String(tag ?? '').trim();
  if (!replacement) return { text: value, caret: Number(caret) || 0 };
  const fragment = activeTagFragment(value, caret);
  const rest = value.slice(fragment.end).replace(/^,\s*/, '');
  const next = `${value.slice(0, fragment.start)}${replacement}, ${rest}`;
  return { text: next, caret: fragment.start + replacement.length + 2 };
}

/** Ước lượng token CLIP (±10%) như prompt_lib/limits.py. */
export function pieceTokens(piece) {
  let total = 0;
  for (const word of String(piece ?? '').split(/\s+/)) {
    if (!word) continue;
    const parts = word.match(/[A-Za-z]+|\d+|[^\sA-Za-z\d]/g) || [];
    for (const part of parts) {
      if (/^\d+$/.test(part)) total += Math.max(1, Math.ceil(part.length / 3));
      else if (/^[A-Za-z]+$/.test(part)) total += Math.max(1, Math.ceil(part.length / 7));
      else total += 1;
    }
  }
  return total;
}

/** Tổng token ước lượng của một prompt (kể cả dấu phẩy phân cách). */
export function estimateTokens(text) {
  const pieces = splitPieces(text).map((p) => p.trim()).filter((p) => p && p !== 'BREAK');
  if (!pieces.length) return 0;
  return pieces.reduce((sum, p) => sum + pieceTokens(p), 0) + (pieces.length - 1);
}

/** Ngân sách 75 / 150 / 225 token -> mức cảnh báo cho UI. */
export function tokenAdvice(tokens) {
  if (tokens <= 75) return { level: 'ok', label: 'chắc', text: 'trong 1 cửa sổ CLIP — mọi tag đều có trọng số' };
  if (tokens <= 150) return { level: 'warn', label: 'còn tốt', text: '2 cửa sổ CLIP — tag đầu vẫn mạnh nhất' };
  return { level: 'bad', label: 'bắt đầu loãng', text: 'từ cửa sổ 3 trở đi chi tiết gần như mất tác dụng' };
}

/**
 * Trộn tag theo thứ tự nhóm chuẩn, khử trùng lặp.
 * `groupOf(tag)` trả về index nhóm (0..GROUP_ORDER.length-1).
 */
export function sortTagsByGroup(pieces, groupOf) {
  const rank = (piece) => {
    const index = typeof groupOf === 'function' ? groupOf(piece.tag) : OTHER_GROUP;
    return Number.isInteger(index) ? index : OTHER_GROUP;
  };
  return pieces
    .map((piece, position) => ({ piece, position, rank: rank(piece) }))
    .sort((a, b) => (a.rank - b.rank) || (a.position - b.position))
    .map((entry) => entry.piece);
}

/** Khử tag trùng nghĩa (giống compact_prompt: bỏ `eyes` khi đã có `blue_eyes`). */
export function dedupePieces(pieces) {
  const seen = new Set();
  const out = [];
  for (const piece of pieces) {
    const key = normKey(piece.tag);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(piece);
  }
  // Lượt 2: bỏ tag 1 từ nằm trong tag nhiều từ đã chọn ("eyes" khi có "blue eyes").
  const multiWord = out
    .filter((p) => normKey(p.tag).includes(' '))
    .map((p) => ` ${normKey(p.tag)} `);
  const kept = out.filter((piece) => {
    if (piece.special) return true;
    const key = normKey(piece.tag);
    if (key.includes(' ')) return true;
    return !multiWord.some((long) => long.includes(` ${key} `));
  });
  return kept.length ? kept : out;
}

/** Danh sách tag hệ thống (không có trong CSV) để UI vẫn tra được nhóm. */
export const SYSTEM_TAGS = {
  quality: ['masterpiece', 'best quality', 'amazing quality', 'high quality', 'newest',
    'highres', 'absurdres', 'very awa'],
  rating: ['rating_general', 'rating_sensitive', 'rating_questionable', 'rating_explicit',
    'general', 'sensitive', 'questionable', 'explicit', 'nsfw'],
};

/** Nhóm của tag hệ thống, hoặc null. */
export function systemGroup(tag) {
  const key = normKey(tag);
  for (const [group, list] of Object.entries(SYSTEM_TAGS)) {
    if (list.some((item) => normKey(item) === key)) return group;
  }
  return null;
}

/**
 * Chuẩn hoá prompt: thêm tag chất lượng + phân loại, sắp theo nhóm, khử trùng lặp.
 * Trả về chuỗi prompt mới (giữ nguyên `<lora:...>` ở cuối).
 */
export function normalisePrompt(text, opts = {}) {
  const { quality = '', ratingPositive = [], groupOf, dropDuplicates = true, extra = '' } = opts;
  const pieces = parseTags(text);
  const specials = pieces.filter((p) => p.special);
  let body = pieces.filter((p) => !p.special);

  if (dropDuplicates) body = dedupePieces(body);
  body = sortTagsByGroup(body, groupOf);

  const present = new Set(body.map((p) => normKey(p.tag)));
  const prefix = [];
  for (const tag of parseTags([quality, ...ratingPositive].filter(Boolean).join(', '))) {
    const key = normKey(tag.tag);
    if (!key || present.has(key)) continue;
    present.add(key);
    prefix.push(tag);
  }

  const extras = extra ? parseTags(extra).filter((p) => !present.has(normKey(p.tag))) : [];
  const all = [...prefix, ...body, ...extras, ...specials];
  return all.map((p) => renderTag(p.tag, p.weight)).join(', ');
}

/** Negative prompt: preset + mức phân loại ngược + phần người dùng nhập, đã khử trùng. */
export function buildNegative({ preset = '', ratingNegative = [], extra = '' } = {}) {
  const seen = new Set();
  const out = [];
  for (const piece of parseTags([preset, (ratingNegative || []).join(', '), extra].filter(Boolean).join(', '))) {
    const key = normKey(piece.tag);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(renderTag(piece.tag, piece.weight));
  }
  return out.join(', ');
}

const SAMPLER_ALIASES = {
  'DPM++ 2M Karras': 'DPM++ 2M',
  'DPM++ 2M SDE Karras': 'DPM++ 2M SDE',
  'DPM++ 3M SDE Karras': 'DPM++ 3M SDE',
};

/**
 * Body cho POST /sdapi/v1/txt2img — bản JS của PromptBuilder.payload().
 * `overrides` thắng `defaults`; khoá `null`/`undefined` bị bỏ qua.
 */
export function buildPayload({ positive, negative, defaults = {}, overrides = {} } = {}) {
  const body = { ...defaults };
  body.prompt = String(positive ?? '');
  body.negative_prompt = String(negative ?? '');
  for (const [key, value] of Object.entries(overrides || {})) {
    if (value === null || value === undefined || value === '') continue;
    body[key] = value;
  }
  body.seed = Number.isFinite(Number(body.seed)) ? Number(body.seed) : -1;

  const mapped = SAMPLER_ALIASES[body.sampler_name];
  if (mapped) {
    body.sampler_name = mapped;
    if (!(overrides || {}).scheduler) body.scheduler = 'Karras';
  }

  const clipSkip = body.clip_skip ?? 2;
  delete body.clip_skip;
  const settings = { ...(body.override_settings || {}) };
  if (!('clip_stop_at_last_layers' in settings)) {
    settings.clip_stop_at_last_layers = clipSkip;
  }
  body.override_settings = settings;
  body.override_settings_restore_afterwards = true;
  if (!body.scheduler) body.scheduler = 'Automatic';

  if (!body.enable_hr) {
    for (const key of ['hr_upscaler', 'hr_scale', 'hr_second_pass_steps', 'denoising_strength']) {
      delete body[key];
    }
  }
  return body;
}

/** Cảnh báo tham số dễ làm hỏng/treo máy — hiện ngay dưới nút Tạo ảnh. */
export function payloadWarnings(payload) {
  const out = [];
  const width = Number(payload.width) || 0;
  const height = Number(payload.height) || 0;
  if (width && height) {
    if (Math.min(width, height) < 512) out.push('Cạnh ngắn dưới 512 px: mặt và tay dễ lỗi.');
    if (Math.max(width, height) > 1536) out.push('Cạnh dài trên 1536 px: SDXL dễ lặp hình, tốn VRAM.');
    if (width % 8 || height % 8) out.push('Kích thước nên là bội số của 8.');
  }
  if (Number(payload.cfg_scale) > 10) out.push('CFG trên 10 dễ bết màu; WAI v17 khuyến nghị 5–7.');
  if (Number(payload.steps) > 40) out.push('Trên 40 bước gần như không đẹp thêm mà chậm gấp đôi.');
  if (Array.isArray(payload.init_images) && Number(payload.denoising_strength) > 0.8) {
    out.push('Denoise img2img trên 0,8 có thể thay gần như toàn bộ ảnh gốc.');
  }
  if (payload.enable_hr) {
    const scale = Number(payload.hr_scale) || 0;
    const target = width * height * scale * scale;
    if (scale > 2) out.push('Hires trên 2× rất dễ hết VRAM trên T4 (16 GB).');
    if (target > 2500000) out.push(`Hires tạo khoảng ${(target / 1000000).toFixed(1)} MP; trên 2,5 MP dễ hết VRAM.`);
    if (Number(payload.hr_second_pass_steps) > 30) out.push('Hires steps trên 30 thường chỉ làm chậm thêm.');
    if (Number(payload.denoising_strength) > 0.6) out.push('Denoise trên 0,6 có thể đổi mạnh bố cục ảnh gốc.');
  }
  if (Number(payload.batch_size) > 1) out.push('Batch > 1 nhân thời gian và VRAM; nên để 1 trên Colab.');
  return out;
}

/** Chặn payload sai mà không tự thay lựa chọn thủ công. */
export function payloadErrors(payload) {
  const out = [];
  const integer = (key, label, min, max) => {
    const value = Number(payload[key]);
    if (!Number.isInteger(value) || value < min || value > max) out.push(`${label} phải là số nguyên ${min}–${max}.`);
  };
  integer('width', 'Chiều rộng', 256, 2048);
  integer('height', 'Chiều cao', 256, 2048);
  integer('steps', 'Steps', 4, 80);
  integer('batch_size', 'Batch', 1, 4);
  if ((Number(payload.width) % 8) || (Number(payload.height) % 8)) out.push('Kích thước phải chia hết cho 8.');
  const cfg = Number(payload.cfg_scale);
  if (!Number.isFinite(cfg) || cfg < 1 || cfg > 30) out.push('CFG phải trong 1–30.');
  const seed = Number(payload.seed);
  if (!Number.isInteger(seed) || seed < -1) out.push('Seed phải là số nguyên từ -1 trở lên.');
  if (payload.enable_hr) {
    const scale = Number(payload.hr_scale);
    const denoise = Number(payload.denoising_strength);
    if (!Number.isFinite(scale) || scale < 1.1 || scale > 2) out.push('Hires scale phải trong 1,1–2.');
    integer('hr_second_pass_steps', 'Hires steps', 1, 60);
    if (!Number.isFinite(denoise) || denoise < 0.1 || denoise > 0.75) out.push('Denoise phải trong 0,1–0,75.');
    if (!String(payload.hr_upscaler || '').trim()) out.push('Chọn Hires upscaler.');
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'init_images')) {
    if (!Array.isArray(payload.init_images) || payload.init_images.length !== 1
      || !String(payload.init_images[0] || '').trim()) {
      out.push('Chọn đúng một ảnh gốc cho img2img.');
    }
    const denoise = Number(payload.denoising_strength);
    if (!Number.isFinite(denoise) || denoise < 0.05 || denoise > 1) {
      out.push('Denoise img2img phải trong 0,05–1.');
    }
    if (![0, 1, 2].includes(Number(payload.resize_mode))) out.push('Chế độ resize img2img không hợp lệ.');
  }
  return out;
}

const URL_IN_TEXT = /https?:\/\/[^\s"'<>)\]}]+/gi;
const BARE_HOSTS = /\b((?:[a-z0-9-]+\.)+(?:gradio\.live|trycloudflare\.com|ngrok-free\.app|ngrok\.io)|\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})\b/gi;
const FORGE_HOSTS = /(gradio\.live|trycloudflare\.com|ngrok|\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})/i;

/**
 * Rút link Forge từ một khối text bất kỳ (clipboard sau khi chạy Colab).
 *
 * Colab in ra đủ thứ: `Link public: https://abc123.gradio.live`, log cloudflared,
 * link nội bộ `http://127.0.0.1:7860`… Hàm này chọn link **dùng được từ điện thoại**:
 * ưu tiên gradio.live / trycloudflare / ngrok, bỏ localhost/127.0.0.1, bỏ link
 * `colab.research.google.com`. Trả `''` nếu không có.
 */
export function extractForgeUrl(text) {
  const raw = String(text ?? '');
  if (!raw.trim()) return '';
  const candidates = [];
  for (const match of raw.match(URL_IN_TEXT) || []) candidates.push(match);
  for (const match of raw.match(BARE_HOSTS) || []) candidates.push(match.replace(/^[a-z]+:\/\//i, ''));

  let best = '';
  let bestScore = -1;
  for (const candidate of candidates) {
    const cleaned = candidate.replace(/[.,;:'")\]}]+$/, '');
    // Host trần kiểu "192.168.1.9:7860" là Forge trong LAN (http), còn link tunnel
    // (gradio.live, trycloudflare, ngrok) luôn https — đoán sai scheme là lỗi im lặng.
    const bareIp = /^\d{1,3}(?:\.\d{1,3}){3}(?::\d{2,5})?(?:\/|$)/.test(cleaned);
    let url;
    try {
      url = normalizeBaseUrl(bareIp ? `http://${cleaned.replace(/^[a-z]+:\/\//i, '')}` : cleaned);
    } catch (error) {
      continue;
    }
    if (!/^https?:\/\//i.test(url)) continue;
    const host = url.replace(/^https?:\/\//i, '').split('/')[0].toLowerCase();
    if (/^(localhost|127\.0\.0\.1|0\.0\.0\.0)(:|$)/.test(host)) continue;
    if (host.includes('colab.research.google.com') || host.includes('github.com')) continue;
    let score = 1;
    if (host.includes('gradio.live')) score = 5;
    else if (host.includes('trycloudflare.com')) score = 4;
    else if (host.includes('ngrok')) score = 3;
    else if (FORGE_HOSTS.test(host)) score = 2;
    // link có đường dẫn lạ (ảnh, docs) ít khả năng là Forge
    if (/\/(file|assets?|static|favicon)/i.test(url)) score -= 1;
    if (score > bestScore) {
      bestScore = score;
      best = url;
    }
  }
  return best;
}

/** Chuẩn hoá URL người dùng dán: bỏ dấu cách, bỏ '/' cuối, thêm https nếu thiếu scheme. */
export function normalizeBaseUrl(input) {
  let url = String(input ?? '').trim();
  if (!url) return '';
  if (!/^https?:\/\//i.test(url)) {
    // Link gradio.live / trycloudflare / IP LAN — mặc định https, riêng IP/host nội bộ
    // vẫn dùng được http nếu người dùng gõ rõ "http://".
    url = `https://${url}`;
  }
  return url.replace(/\/+$/, '');
}

/**
 * URL tuyệt đối cho endpoint API; `base` rỗng = cùng origin với trang đang mở.
 *
 * Phải bắt đầu bằng `/` (không phải `./`): app có thể được phục vụ dưới
 * `/vi-mobile/` (route của extension Forge), khi đó `./sdapi/...` sẽ thành
 * `/vi-mobile/sdapi/...` và 404.
 */
export function apiUrl(base, path) {
  const clean = String(path ?? '').replace(/^\/+/, '');
  const root = base ? normalizeBaseUrl(base) : '';
  return root ? `${root}/${clean}` : `/${clean}`;
}

/** Câu thông báo tiến trình tiếng Việt từ /sdapi/v1/progress. */
export function progressText(info, elapsedSeconds = 0) {
  if (!info || info.available === false) {
    return elapsedSeconds
      ? `⏳ đã ${formatDuration(elapsedSeconds)} · chưa đọc được tiến trình`
      : '⏳ đã gửi yêu cầu tới Forge…';
  }
  const percent = Math.round((Number(info.progress) || 0) * 100);
  const step = Number(info.step) || 0;
  const steps = Number(info.steps) || 0;
  const parts = [];
  if (elapsedSeconds) parts.push(`⏳ ${formatDuration(elapsedSeconds)}`);
  if (percent) parts.push(`${percent}%`);
  if (steps) parts.push(`bước ${step}/${steps}`);
  if (Number(info.eta) > 0) parts.push(`còn ~${formatDuration(Number(info.eta))}`);
  return parts.join(' · ') || '⏳ Forge đang chạy…';
}

/** 75 -> "1m 15s". */
export function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (!minutes) return `${rest}s`;
  return `${minutes}m ${String(rest).padStart(2, '0')}s`;
}

/** Dịch lỗi HTTP/mạng sang việc cần làm (tiếng Việt). */
export function explainError(status, bodyText = '') {
  const body = String(bodyText || '').slice(0, 400);
  if (!status) {
    return 'Không gọi được máy chủ: kiểm tra URL Forge, Wi-Fi/4G, và link tunnel còn sống '
      + '(link gradio.live hết hạn sau vài giờ). Nếu app cài riêng (APK) mà app chạy trên '
      + 'trình duyệt thì Forge phải bật --cors-allow-origins.';
  }
  if (status === 401 || status === 403) {
    return 'Máy chủ yêu cầu đăng nhập (--api-auth). Nhập tài khoản API trong Cài đặt.';
  }
  if (status === 404) {
    return 'Không thấy /sdapi: Forge phải chạy với cờ --api (bộ cài đã bật sẵn).';
  }
  if (status === 422 || status === 400) {
    return `Tham số bị từ chối${body ? `: ${body}` : ''}. Thử giảm kích thước hoặc tắt Hires.`;
  }
  if (status === 500 || status === 502 || status === 503) {
    return 'Forge trả lỗi: thường do hết VRAM hoặc đang nạp checkpoint. Xem forge.log, '
      + 'giảm kích thước/tắt Hires rồi thử lại.';
  }
  if (status === 504) return 'Tunnel quá thời gian chờ. Ảnh có thể vẫn xong trên Forge — thử lại sau.';
  return `Máy chủ trả HTTP ${status}${body ? `: ${body}` : ''}.`;
}

/** `info` của Forge có thể là object hoặc chuỗi JSON — chuẩn hoá về object. */
function coerceInfo(info) {
  if (typeof info === 'string') {
    try {
      return JSON.parse(info);
    } catch (error) {
      return {};
    }
  }
  return info && typeof info === 'object' ? info : {};
}

/** Lấy seed đã dùng cho ảnh từ `info` của Forge. */
export function seedFromInfo(rawInfo) {
  const info = coerceInfo(rawInfo);
  const seed = info.seed ?? (info.all_seeds && info.all_seeds[0]);
  return Number.isFinite(Number(seed)) ? Number(seed) : null;
}

/** Prompt/negative/seed của ảnh đã tạo, để "dùng lại" từ thư viện. */
export function reuseFromInfo(rawInfo) {
  const info = coerceInfo(rawInfo);
  return {
    prompt: typeof info.prompt === 'string' ? info.prompt : '',
    negative: typeof info.negative_prompt === 'string' ? info.negative_prompt : '',
    seed: seedFromInfo(info),
  };
}
