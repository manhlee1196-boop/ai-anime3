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
  sampler: 'Euler a',
  steps: 25,
  cfg: 6,
  sizeIndex: 0,               // chỉ số trong presets.sizes
  hires: true,
  hrScale: 1.5,
  denoise: 0.4,
  clipSkip: 2,
  batch: 1,
  seed: -1,
  rating: 'general',
  qualityPreset: 'WAI khuyến nghị (đầy đủ)',
  negativePreset: 'WAI khuyến nghị (ngắn)',
  negativeExtra: '',
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
 * `record` = {id, dataUrl, prompt, negative, seed, info, params, createdAt}
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

/** Ảnh mới nhất trước. Chỉ trả metadata + data URL (đủ để vẽ lưới). */
export async function listImages({ limit = 60, offset = 0 } = {}) {
  const db = await openDb();
  if (!db) return memoryFallback.slice(offset, offset + limit);
  const items = await new Promise((resolve) => {
    const request = tx(db, 'readonly').getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => resolve([]);
  });
  items.sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
  return items.slice(offset, offset + limit);
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
