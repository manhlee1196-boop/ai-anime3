"""Lịch sử ảnh trên đĩa: chỉ mục SQLite + thumbnail, không giữ PIL/tensor trong RAM.

Đọc ảnh đã lưu bởi Forge/notebook; không sửa/xoá ảnh gốc hoặc metadata của chúng.
Không import Gradio/torch. Pillow chỉ được import khi đọc header hoặc làm preview.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PAGE_SIZE = 24
MAX_SCAN_FILES = 50000
MAX_PREVIEW_PIXELS = 4096 * 4096
THUMB_SIZE = (384, 384)
PARAMETER_LIMIT = 65536


def forge_output_roots(forge_dir, options=None):
    """Tôn trọng thư mục output cấu hình; chỉ thêm thư mục output chuyên dụng cũ."""
    base = Path(forge_dir).expanduser().resolve()
    roots = [base / "output", base / "outputs"]
    for key in ("outdir_samples", "outdir_txt2img_samples", "outdir_img2img_samples",
                "outdir_extras_samples", "outdir_save", "outdir_grids",
                "outdir_txt2img_grids", "outdir_img2img_grids"):
        value = options.get(key) if isinstance(options, dict) else getattr(options, key, None)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser()
            roots.append(path if path.is_absolute() else base / path)
    return roots


def _seed_from_parameters(value):
    if not isinstance(value, str):
        return None
    value = value[-PARAMETER_LIMIT:]
    seed = None
    if value.lstrip().startswith("{"):
        try:
            seed = json.loads(value).get("seed")
        except (ValueError, AttributeError):
            pass
    else:
        # Không lấy chữ "Seed:" trong prompt/negative; đọc dòng sampling cuối.
        lines = [line for line in value.splitlines() if line.lstrip().startswith("Steps:")]
        if lines:
            match = re.search(r"(?:^|,\s*)Seed:\s*(-?\d+)(?=\s*(?:,|$))", lines[-1])
            if match:
                seed = int(match.group(1))
    return seed if type(seed) is int and 0 <= seed <= 4294967295 else None


def _parameters(image):
    value = image.info.get("parameters")
    if isinstance(value, str):
        return value
    try:
        exif = image.getexif()
        comment = exif.get(37510) or exif.get_ifd(34665).get(37510)
        if isinstance(comment, bytes):
            if comment.startswith(b"UNICODE\0"):
                raw = comment[8:]
                return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-16-be", errors="replace")
            return comment.removeprefix(b"ASCII\0\0\0").decode("utf-8", errors="replace")
        return comment if isinstance(comment, str) else ""
    except (ValueError, KeyError, TypeError, OSError):
        return ""


@dataclass(frozen=True)
class HistoryImage:
    id: int
    path: str
    mtime_ns: int
    size: int
    width: int
    height: int
    seed: int | None
    is_grid: bool

    def table_row(self):
        return [datetime.fromtimestamp(self.mtime_ns / 1e9, timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M:%S"),
                Path(self.path).name, "Ảnh lưới" if self.is_grid else (str(self.seed) if self.seed is not None else "—"),
                f"{self.width}×{self.height}", f"{self.size / 1048576:.2f} MiB"]


class ImageHistory:
    def __init__(self, roots, cache_dir):
        paths = sorted({Path(p).expanduser().resolve() for p in roots if str(p).strip()}, key=lambda p: (len(p.parts), str(p)))
        self.roots = tuple(p for i, p in enumerate(paths) if not any(p.is_relative_to(parent) for parent in paths[:i]))
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.db_path = self.cache_dir / "images.sqlite3"
        self.thumb_dir = self.cache_dir / "previews"
        self._lock = threading.RLock()
        self.scan_limited = False

    def _connect(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.db_path.is_symlink():
            raise OSError("Chỉ mục lịch sử không được là symlink")
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA cache_size=-2048")  # khoảng 2 MiB, không cache tất cả bản ghi
        connection.execute("""CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE NOT NULL,
            root TEXT NOT NULL, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL,
            width INTEGER NOT NULL, height INTEGER NOT NULL, seed INTEGER,
            is_grid INTEGER NOT NULL, seen INTEGER NOT NULL)""")
        connection.execute("CREATE INDEX IF NOT EXISTS images_newest ON images(mtime_ns DESC, id DESC)")
        return connection

    def _safe_path(self, value):
        path = Path(value)
        try:
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                return None
            # Không theo symlink thư mục: cả đường dẫn tuyệt đối và canonical phải giống nhau.
            if path.absolute() != path.resolve():
                return None
            return path if any(path.is_relative_to(root) for root in self.roots) else None
        except (OSError, ValueError):
            return None

    def _files(self):
        count = 0
        for root in self.roots:
            if not root.is_dir():
                continue
            stack = [(root, 0)]
            while stack:
                folder, depth = stack.pop()
                try:
                    with os.scandir(folder) as entries:
                        for entry in entries:
                            if entry.name.startswith(".") or entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                if depth < 8:
                                    stack.append((Path(entry.path), depth + 1))
                                continue
                            if entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                                count += 1
                                if count > MAX_SCAN_FILES:
                                    self.scan_limited = True
                                    return
                                yield root, Path(entry.path)
                except OSError:
                    # Không xoá index nếu thư mục tạm thời không đọc được.
                    self.scan_limited = True

    def refresh(self):
        from PIL import Image
        with self._lock:
            connection = self._connect()
            try:
                self.scan_limited = False
                seen = time.time_ns()
                for root, candidate in self._files():
                    path = self._safe_path(candidate)
                    if path is None:
                        continue
                    try:
                        stat = path.stat()
                        old = connection.execute("SELECT mtime_ns,size FROM images WHERE path=?", (str(path),)).fetchone()
                        if old and old["mtime_ns"] == stat.st_mtime_ns and old["size"] == stat.st_size:
                            connection.execute("UPDATE images SET seen=? WHERE path=?", (seen, str(path)))
                            continue
                        with Image.open(path) as image:
                            if image.format not in {"PNG", "JPEG", "WEBP"}:
                                continue
                            width, height = image.size
                            parameters = _parameters(image)
                        if not parameters:
                            sidecar = path.with_suffix(".txt")
                            if not sidecar.is_symlink() and sidecar.is_file():
                                with sidecar.open(encoding="utf-8", errors="replace") as stream:
                                    parameters = stream.read(PARAMETER_LIMIT)
                        grid = path.stem.lower().startswith("grid-") or any(p.lower().endswith("grids") for p in path.relative_to(root).parts[:-1]) or root.name.lower().endswith("grids")
                        seed = None if grid else _seed_from_parameters(parameters)
                        # Notebook sample có seed trong tên nếu không có PNG parameters.
                        match = re.search(r"_seed(\d+)$", path.stem)
                        if seed is None and not grid and match and path.stem.startswith("wai17_"):
                            seed = int(match.group(1))
                            if seed > 4294967295:
                                seed = None
                        connection.execute("""INSERT INTO images(path,root,mtime_ns,size,width,height,seed,is_grid,seen)
                            VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                            root=excluded.root,mtime_ns=excluded.mtime_ns,size=excluded.size,
                            width=excluded.width,height=excluded.height,seed=excluded.seed,
                            is_grid=excluded.is_grid,seen=excluded.seen""",
                            (str(path), str(root), stat.st_mtime_ns, stat.st_size, width, height, seed, int(grid), seen))
                    except (OSError, ValueError, Image.DecompressionBombError):
                        continue  # file đang ghi/hỏng: lần refresh sau đọc lại; không dump prompt/path riêng
                if not self.scan_limited and self.roots:
                    marks = ",".join("?" for _ in self.roots)
                    connection.execute(f"DELETE FROM images WHERE root IN ({marks}) AND seen<>?", (*map(str, self.roots), seen))
                connection.commit()
            finally:
                connection.close()

    @staticmethod
    def _record(row):
        return HistoryImage(**{key: (bool(row[key]) if key == "is_grid" else row[key])
                               for key in ("id", "path", "mtime_ns", "size", "width", "height", "seed", "is_grid")})

    def page(self, number=1, size=12):
        number, size = max(1, int(number)), max(1, min(MAX_PAGE_SIZE, int(size)))
        with self._lock:
            connection = self._connect()
            try:
                if not self.roots:
                    return [], 0, 1, 1
                marks = ",".join("?" for _ in self.roots)
                roots = tuple(map(str, self.roots))
                total = connection.execute(f"SELECT COUNT(*) FROM images WHERE root IN ({marks})", roots).fetchone()[0]
                pages = max(1, (total + size - 1) // size)
                number = min(number, pages)
                rows = connection.execute(f"SELECT * FROM images WHERE root IN ({marks}) ORDER BY mtime_ns DESC,id DESC LIMIT ? OFFSET ?",
                                          (*roots, size, (number - 1) * size)).fetchall()
                return [self._record(row) for row in rows], total, number, pages
            finally:
                connection.close()

    def get(self, image_id):
        if type(image_id) is not int or image_id <= 0:
            return None
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
            finally:
                connection.close()
            if row is None:
                return None
            record = self._record(row)
            path = self._safe_path(record.path)
            if path is None:
                return None
            try:
                stat = path.stat()
                return record if (stat.st_mtime_ns, stat.st_size) == (record.mtime_ns, record.size) else None
            except OSError:
                return None

    def thumbnail(self, record):
        """Chỉ trả filepath; một ảnh được decode tại một thời điểm, không giữ PIL trong State."""
        from PIL import Image, ImageDraw, ImageOps
        with self._lock:
            if self.get(record.id) != record:
                return None
            key = hashlib.sha256(f"{record.path}\0{record.mtime_ns}\0{record.size}".encode()).hexdigest()
            if self.thumb_dir.is_symlink():
                raise OSError("Thư mục preview không được là symlink")
            self.thumb_dir.mkdir(parents=True, exist_ok=True)
            dest = self.thumb_dir / f"wai-thumb-{key}.webp"
            if dest.is_file() and not dest.is_symlink():
                return str(dest)
            tmp = dest.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                if record.width * record.height > MAX_PREVIEW_PIXELS:
                    with Image.new("RGB", (320, 180), "#edf1f7") as placeholder:
                        ImageDraw.Draw(placeholder).text((35, 75), "Anh lon - chon de xem anh goc", fill="#34455d")
                        placeholder.save(tmp, format="WEBP", quality=80)
                else:
                    with Image.open(record.path) as image:
                        image.draft("RGB", THUMB_SIZE)
                        image.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
                        with ImageOps.exif_transpose(image) as preview:
                            if preview.mode not in {"RGB", "RGBA", "L"}:
                                with preview.convert("RGB") as rgb:
                                    rgb.save(tmp, format="WEBP", quality=80)
                            else:
                                preview.save(tmp, format="WEBP", quality=80)
                tmp.replace(dest)
                return str(dest)
            except (OSError, ValueError, Image.DecompressionBombError):
                return None
            finally:
                if tmp.exists():
                    tmp.unlink()
