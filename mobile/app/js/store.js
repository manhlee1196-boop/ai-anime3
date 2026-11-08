/**
 * Lưu trữ trên máy: cài đặt (localStorage) và ảnh đã tạo (IndexedDB).
 *
 * Ảnh SDXL là ảnh lớn (0,5–3 MB/ảnh) nên **không** nhét vào localStorage (giới hạn
 * ~5 MB) — IndexedDB chịu được hàng trăm ảnh và không chặn UI.
 */

const SETTINGS_KEY = 'anime3.mobile.settings.v1';
const DB_NAME = 'anime3-mobile';
const DB_VERSION = 1;
const STORE = 'images';

/** Cài đặt mặc định — tham số theo thẻ model WAI-Illustrious v17.0. */
export const DEFAULT_SETTINGS = {
  apiUrl: '',                 // '' = cùng origin với trang đang mở
  user: '',
  pass: '',
  generationMode: 'txt2img',    // txt2img | img2img
  sampler: 'Euler a',
  steps: 25,
  cfg: 6,
  sizeIndex: 5,               // 832×1216: mặc định an toàn cho T4
  hires: false,               // opt-in to avoid unexpected VRAM and render time
  hrScale: 1.5,
  hrSteps: 12,
  hrUpscaler: 'RealESRGAN_x4plus_anime_6B',
  denoise: 0.35,
  img2imgDenoise: 0.55,
  img2imgResizeMode: 1,         // 0 kéo giãn · 1 cắt giữa · 2 giữ tỉ lệ + nền
  clipSkip: 2,
  batch: 1,
  seed: -1,
  rating: 'general',
  qualityPreset: 'WAI khuyến nghị (đầy đủ)',
  negativePreset: 'WAI khuyến nghị (ngắn)',
  negativeExtra: '',
  autoConnect: true,          // tự nhận link Forge trong clipboard khi quay lại app
  links: [],                  // [{url, at, ok, model}] — 6 link gần nhất
};

export function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_SETTINGS, ...(parsed && typeof parsed === 'object' ? parsed : {}) };
  } catch (error) {
    return { ...DEFAULT_SETTINGS };
  }
}

/**
 * Ghi nhớ một link Forge vừa dùng (mới nhất lên đầu, tối đa `max`).
 * Trả về danh sách mới để UI vẽ lại.
 */
export function rememberLink(settings, url, { ok = null, model = '' } = {}) {
  const clean = String(url || '').trim().replace(/\/+$/, '');
  if (!clean) return settings.links || [];
  const list = (settings.links || []).filter((item) => item.url !== clean);
  list.unshift({ url: clean, at: Date.now(), ok, model });
  settings.links = list.slice(0, 6);
  return settings.links;
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    return true;
  } catch (error) {
    console.warn('Không lưu được cài đặt', error);
    return false;
  }
}

// ------------------------------------------------------------------ ảnh đã tạo
let dbPromise = null;
const memoryFallback = [];

/** Mở IndexedDB; nếu trình duyệt chặn (chế độ riêng tư) thì dùng mảng trong RAM. */
function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    if (typeof indexedDB === 'undefined') {
      resolve(null);
      return;
    }
    let request;
    try {
      request = indexedDB.open(DB_NAME, DB_VERSION);
    } catch (error) {
      resolve(null);
      return;
    }
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id' });
        store.createIndex('createdAt', 'createdAt');
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
  });
  return dbPromise;
}

function tx(db, mode) {
  return db.transaction(STORE, mode).objectStore(STORE);
}

/**
 * Thêm một ảnh vào thư viện.
 * `record` = {id, blob, name, mime, prompt, negative, seed, info, params, createdAt}
 * Bản cũ có dataUrl vẫn đọc được; bản mới lưu Blob để tránh base64 trong RAM.
 */
export async function addImage(record) {
  const item = {
    id: record.id || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: record.createdAt || Date.now(),
    ...record,
  };
  const db = await openDb();
  if (!db) {
    memoryFallback.unshift(item);
    return item;
  }
  await new Promise((resolve, reject) => {
    const request = tx(db, 'readwrite').put(item);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
  return item;
}

/**
 * Ảnh mới nhất trước, **chỉ metadata + thumbnail**.
 *
 * Không trả data URL của ảnh gốc: 60 ảnh SDXL là ~100 MB base64, đủ làm treo WebView
 * trên máy yếu. Ảnh gốc lấy riêng bằng `getImage(id)` khi người dùng mở ảnh.
 */
export async function listImages({ limit = 60, offset = 0 } = {}) {
  const light = (item) => ({
    id: item.id,
    createdAt: item.createdAt || 0,
    seed: item.seed ?? null,
    prompt: item.prompt || '',
    thumb: item.thumb || '',
  });
  const db = await openDb();
  if (!db) {
    return memoryFallback
      .slice()
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
      .slice(offset, offset + limit)
      .map(light);
  }
  return new Promise((resolve) => {
    const out = [];
    let skipped = 0;
    const request = tx(db, 'readonly').index('createdAt').openCursor(null, 'prev');
    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor || out.length >= limit) {
        resolve(out);
        return;
      }
      if (skipped < offset) {
        skipped += 1;
      } else {
        out.push(light(cursor.value));
      }
      cursor.continue();
    };
    request.onerror = () => resolve(out);
  });
}

export async function countImages() {
  const db = await openDb();
  if (!db) return memoryFallback.length;
  return new Promise((resolve) => {
    const request = tx(db, 'readonly').count();
    request.onsuccess = () => resolve(request.result || 0);
    request.onerror = () => resolve(0);
  });
}

export async function getImage(id) {
  const db = await openDb();
  if (!db) return memoryFallback.find((item) => item.id === id) || null;
  return new Promise((resolve) => {
    const request = tx(db, 'readonly').get(id);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => resolve(null);
  });
}

export async function deleteImage(id) {
  const db = await openDb();
  if (!db) {
    const index = memoryFallback.findIndex((item) => item.id === id);
    if (index >= 0) memoryFallback.splice(index, 1);
    return;
  }
  await new Promise((resolve) => {
    const request = tx(db, 'readwrite').delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
  });
}

export async function clearImages() {
  const db = await openDb();
  if (!db) {
    memoryFallback.length = 0;
    return;
  }
  await new Promise((resolve) => {
    const request = tx(db, 'readwrite').clear();
    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
  });
}
