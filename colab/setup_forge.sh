#!/usr/bin/env bash
# =============================================================================
#  WAI-Illustrious v17 + Forge Neo trên Google Colab
#  Kho prompt: danbooru_e621 (bản dịch tiếng Việt) + bộ dựng prompt tiếng Việt
#
#  Cách dùng (từ notebook, mỗi ô gọi một stage):
#      bash colab/setup_forge.sh gpu        # xem GPU / ổ đĩa / RAM
#      bash colab/setup_forge.sh repo       # clone repo chứa kho prompt
#      bash colab/setup_forge.sh forge      # cài Forge Neo (uv + Python 3.13)
#      bash colab/setup_forge.sh torch      # cài PyTorch đúng với driver, có dự phòng
#      bash colab/setup_forge.sh model      # tải WAI v17 (6,5 GB) + kiểm SHA256
#      bash colab/setup_forge.sh extras     # tagcomplete + kho prompt + extension VN
#      bash colab/setup_forge.sh launch     # chạy Forge (chặn ô, in link gradio.live)
#      bash colab/setup_forge.sh launch-bg  # chạy nền, in link rồi trả lại ô
#      bash colab/setup_forge.sh all        # gpu -> extras (không launch)
#
#  Mọi đường dẫn/URL đều ghi đè được bằng biến môi trường (xem khối CONFIG).
# =============================================================================
# shellcheck disable=SC2034 # marker API được install.sh đọc trước khi gọi stage
SETUP_API_VERSION=2
set -Eeuo pipefail
trap 'rc=$?; printf "\n✖ Stage %s lỗi (dòng %s, mã %s). Không đánh dấu hoàn tất.\n" "${1:-all}" "$LINENO" "$rc" >&2; exit "$rc"' ERR

# ------------------------------------------------------------------- CONFIG
FORGE_DIR="${FORGE_DIR:-/content/sd-webui-forge-neo}"
FORGE_REPO="${FORGE_REPO:-https://github.com/Haoming02/sd-webui-forge-classic}"
FORGE_BRANCH="${FORGE_BRANCH:-neo}"
REPO_DIR="${REPO_DIR:-/content/ai-anime3}"
REPO_URL="${REPO_URL:-https://github.com/manhlee1196-boop/ai-anime3}"
REPO_BRANCH="${REPO_BRANCH:-arena/88f01d31-ai-anime3}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"          # chỉ cần nếu repo để private
PORT="${PORT:-7860}"
TUNNEL="${TUNNEL:-share}"                 # share | cloudflared | none
VRAM_FLAG="${VRAM_FLAG:-}"                # ví dụ: --lowvram  (T4 16GB thường để trống)
RUNTIME_DIR="${WAI_RUNTIME_DIR:-/content}"
TORCH_ENV_FILE="${TORCH_ENV_FILE:-$RUNTIME_DIR/.wai_torch_env}"
FORGE_LOG="$RUNTIME_DIR/forge.log"
FORGE_PID_FILE="$RUNTIME_DIR/forge.pid"
TUNNEL_LOG="$RUNTIME_DIR/cloudflared.log"
TUNNEL_PID_FILE="$RUNTIME_DIR/cloudflared.pid"
LAUNCH_TIMEOUT="${LAUNCH_TIMEOUT:-1200}"
EXTRA_FORGE_ARGS="${EXTRA_FORGE_ARGS:-}"

MODEL_DIR="${MODEL_DIR:-$FORGE_DIR/models/Stable-diffusion}"
MODEL_FILE="${MODEL_FILE:-waiIllustriousSDXL_v170.safetensors}"
MODEL_LABEL="${MODEL_LABEL:-WAI-illustrious-SDXL v17.0 FP16 (6,5 GB)}"
MODEL_SHA256="${MODEL_SHA256-f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04}"
# Ngưỡng dung lượng tối thiểu để coi file tải dở là hỏng (byte).
MODEL_MIN_BYTES="${MODEL_MIN_BYTES:-6800000000}"
CIVITAI_VERSION_ID="${CIVITAI_VERSION_ID-2883731}"
CIVITAI_TOKEN="${CIVITAI_TOKEN:-}"
# MODEL_URL (cách nhau bằng dấu cách) ghi đè TOÀN BỘ danh sách nguồn — dùng khi
# cài biến thể khác FP16, để không tải nhầm mirror FP16 vào tên file FP8.
# Để trống thì dùng mirror HuggingFace của bản FP16 (tải không cần token,
# SHA256 đã đối chiếu với bản Civitai gốc).
if [[ ${MODEL_URL+x} ]]; then
  read -r -a MODEL_URLS <<< "$MODEL_URL"
else
  MODEL_URLS=(
    "https://huggingface.co/LyliaEngine/waiIllustriousSDXL_v170/resolve/main/waiIllustriousSDXL_v170.safetensors"
    "https://huggingface.co/Coercer/Modified_VeryFast_Models_DMD2/resolve/main/Orig_Models_Pruned/waiIllustriousSDXL_v170.safetensors"
  )
fi
UPSCALER_DIR="${UPSCALER_DIR:-$FORGE_DIR/models/ESRGAN}"
UPSCALER_URL="${UPSCALER_URL:-https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth}"
TAC_REPO="${TAC_REPO:-https://github.com/DominikDoom/a1111-sd-webui-tagcomplete}"
PY="${PY:-python3}"

# ------------------------------------------------------------------- tiện ích
c()   { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info(){ c '1;36' "▶ $*"; }
ok()  { c '1;32' "✔ $*"; }
warn(){ c '1;33' "⚠ $*"; }
die() { c '1;31' "✖ $*" >&2; exit 1; }
step(){ echo; c '1;35' "═══ $* ═══"; }

need() { command -v "$1" >/dev/null 2>&1 || die "thiếu lệnh '$1' — hãy cài trước."; }

# ------------------------------------------------------------------- gpu
stage_gpu() {
  step "Kiểm tra môi trường Colab"
  mkdir -p "$RUNTIME_DIR"
  command -v nvidia-smi >/dev/null 2>&1 || die "Không thấy nvidia-smi: hãy bật GPU (Runtime > Change runtime type > T4/L4/A100)."
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
  echo
  # phiên bản CUDA mà driver hỗ trợ -> quyết định chọn wheel torch nào
  CUDA_VER="$(nvidia-smi | grep -oE 'CUDA Version: [0-9.]+' | grep -oE '[0-9]+\.[0-9]+' | head -1)"
  CUDA_MAJOR="${CUDA_VER%%.*}"
  echo "Driver hỗ trợ CUDA: ${CUDA_VER:-không rõ}"
  if [[ "${CUDA_MAJOR:-0}" -ge 13 ]]; then
    echo "TORCH_INDEX=cu130" > "$TORCH_ENV_FILE"
  else
    echo "TORCH_INDEX=cu128" > "$TORCH_ENV_FILE"
    warn "Driver chưa hỗ trợ CUDA 13 -> sẽ dùng wheel cu128 (tự động dự phòng nếu vẫn lỗi)."
  fi
  echo
  df -h /content | tail -1
  echo "RAM: $(free -g | awk '/^Mem/{print $2" GB (khả dụng "$7" GB)"}')"
  [[ -d /content/drive ]] && echo "Google Drive: đã mount" || echo "Google Drive: chưa mount (bạn đã chọn lưu trong /content nên không cần)"
  ok "Xong bước kiểm tra."
}

# ------------------------------------------------------------------- repo
stage_repo() {
  step "Lấy kho prompt"
  if [[ -s "$REPO_DIR/danbooru_e621.csv" ]]; then
    ok "Kho prompt đã có ở $REPO_DIR — không clone/reset lại."; return 0
  fi
  need git
  [[ ! -e "$REPO_DIR" || -z "$(ls -A "$REPO_DIR" 2>/dev/null)" ]] \
    || die "Thư mục $REPO_DIR có dữ liệu nhưng thiếu CSV. Không tự xoá; kiểm tra lại đường dẫn/nhánh."
  mkdir -p "$(dirname "$REPO_DIR")"
  local tmp auth rc=0
  tmp=$(mktemp -d "$(dirname "$REPO_DIR")/.wai-repo.XXXXXX")
  if [[ -n "$GITHUB_TOKEN" ]]; then
    auth=$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.https://github.com/.extraheader \
      GIT_CONFIG_VALUE_0="Authorization: Basic $auth" \
      git clone --quiet --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$tmp" 2>/dev/null || rc=$?
  else
    git clone --quiet --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$tmp" 2>/dev/null || rc=$?
  fi
  if (( rc )); then
    rm -rf -- "$tmp"
    die "Không clone được đúng nhánh $REPO_BRANCH. Kiểm tra URL/nhánh/quyền đọc repo."
  fi
  [[ ! -d "$REPO_DIR" ]] || rmdir -- "$REPO_DIR"
  mv "$tmp" "$REPO_DIR"
  [[ -s "$REPO_DIR/danbooru_e621.csv" ]] || die "Repo không có kho prompt; kiểm tra nhánh."
  ok "Clone xong kho prompt."
}

# ------------------------------------------------------------------- forge
stage_forge() {
  step "Cài Forge Neo ($FORGE_BRANCH)"
  need git
  if [[ ! -d "$FORGE_DIR/.git" ]]; then
    git clone --depth 1 --branch "$FORGE_BRANCH" "$FORGE_REPO" "$FORGE_DIR" \
      || die "Không clone được Forge Neo. Thử lại hoặc đổi FORGE_BRANCH."
  else
    ok "Forge đã có sẵn ở $FORGE_DIR."
  fi
  cd "$FORGE_DIR" || die "không vào được $FORGE_DIR"

  [[ -s "$FORGE_DIR/launch.py" ]] || die "Thư mục Forge thiếu launch.py; không coi clone dở là đã cài."
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    info "Cài uv (trình quản lý gói nhanh)"
    $PY -m pip install --quiet uv 2>/dev/null \
      || curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
  need uv

  if [[ ! -x "$FORGE_DIR/venv/bin/python" ]]; then
    info "Tạo môi trường ảo Python 3.13"
    uv venv venv --python 3.13 --seed || die "uv không tạo được venv Python 3.13."
  fi
  ok "venv: $("$FORGE_DIR/venv/bin/python" -V)"
}

# ------------------------------------------------------------------- torch
stage_torch() {
  step "Cài PyTorch phù hợp với driver"
  local venvpy="$FORGE_DIR/venv/bin/python"
  [[ -x "$venvpy" ]] || die "Chạy stage 'forge' trước."
  local requested="${TORCH_INDEX:-}"
  # shellcheck disable=SC1090 # file do stage torch tạo trong runtime của người dùng
  [[ ! -f "$TORCH_ENV_FILE" ]] || source "$TORCH_ENV_FILE"
  TORCH_INDEX="${requested:-${TORCH_INDEX:-cu130}}"
  case "$TORCH_INDEX" in cu130|cu128|cu126) ;; *) die "TORCH_INDEX không hợp lệ: $TORCH_INDEX" ;; esac

  # Thứ tự thử: bắt đầu từ bản hợp với driver (TORCH_INDEX) rồi lùi dần, khử trùng lặp.
  local order=(cu130 cu128 cu126)
  local i start=0
  for i in "${!order[@]}"; do
    [[ "${order[$i]}" == "$TORCH_INDEX" ]] && { start=$i; break; }
  done
  local candidates=() idx
  for ((i = start; i < ${#order[@]}; i++)); do
    idx="${order[$i]}"
    if [[ "$idx" == "cu130" ]]; then
      candidates+=("cu130|torch==2.13.0+cu130 torchvision==0.28.0+cu130")
    else
      candidates+=("$idx|torch torchvision")
    fi
  done

  local check='import torch,torchvision
print("torch", torch.__version__, "torchvision", torchvision.__version__)
assert torch.cuda.is_available(), "CUDA không khả dụng"
x = torch.ones(16, device="cuda")
assert x.sum().item() == 16
# is_available() có thể True ngay cả khi wheel không chứa kernel cho GPU T4.
torch.cuda.synchronize()'

  if [[ "${FORCE_TORCH:-0}" != 1 ]] && "$venvpy" -c "$check" >/dev/null 2>&1; then
    ok "PyTorch đang có đã chạy được kernel CUDA — giữ nguyên."
    return 0
  fi

  local pkgs
  local -a packages=()
  for entry in "${candidates[@]}"; do
    idx="${entry%%|*}"; pkgs="${entry#*|}"
    info "Thử $idx: pip install $pkgs"
    read -r -a packages <<< "$pkgs"
    "$venvpy" -m pip install --quiet --upgrade --force-reinstall --no-cache-dir "${packages[@]}" --index-url "https://download.pytorch.org/whl/$idx" \
      || { warn "cài $idx thất bại, thử bản khác"; continue; }
    if "$venvpy" -c "$check"; then
      ok "PyTorch $idx dùng được với GPU này."
      # ghi lại để launch.py không cài đè bản khác
      mkdir -p "$(dirname "$TORCH_ENV_FILE")"
      cat > "$TORCH_ENV_FILE" <<EOF
TORCH_INDEX=$idx
export TORCH_INDEX_URL="https://download.pytorch.org/whl/$idx"
export TORCH_COMMAND="pip install $pkgs --index-url https://download.pytorch.org/whl/$idx"
export GRADIO_PACKAGE="gradio==4.40.0 gradio_rangeslider==0.0.8"
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD="true"
EOF
      return 0
    fi
    warn "$idx cài được nhưng torch.cuda.is_available() = False, thử bản cũ hơn."
  done
  die "Không bản PyTorch nào chạy được với GPU/driver này. Kiểm tra lại loại GPU của runtime Colab."
}

# ------------------------------------------------------------------- checkpoint helper
checkpoint_helper() {
  local helper="$REPO_DIR/colab/checkpoint_tools.py"
  if [[ ! -s "$helper" ]]; then
    helper="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checkpoint_tools.py"
  fi
  [[ -s "$helper" ]] || die "Thiếu checkpoint_tools.py. Cập nhật repo; không trộn script cũ/mới."
  printf '%s\n' "$helper"
}
configure_checkpoint() {
  local mid="${WAI_PROFILE_MODEL_ID:-fp16}" cfg="${WAI_PROFILE_CFG:-6.0}"
  local steps="${WAI_PROFILE_STEPS:-25}" hires="${WAI_PROFILE_HIRES_STEPS:-20}"
  # Khi gọi setup trực tiếp vẫn áp dụng đúng preset của bản turbo/lượng tử hoá.
  if [[ "$mid" == hswq ]]; then
    cfg="${WAI_PROFILE_CFG:-1.0}"; steps="${WAI_PROFILE_STEPS:-10}"; hires="${WAI_PROFILE_HIRES_STEPS:-10}"
  elif [[ "$mid" == fp8 || "$mid" == int8 ]]; then
    cfg="${WAI_PROFILE_CFG:-6.5}"
  fi
  "$PY" "$(checkpoint_helper)" configure "$FORGE_DIR" "$MODEL_DIR/$MODEL_FILE" \
    --sha "$MODEL_SHA256" --model-id "$mid" --cfg "$cfg" --steps "$steps" --hires-steps "$hires"
}

# ------------------------------------------------------------------- model
fetch() {  # fetch <url> <đích tạm> [header]; giữ phần đã tải khi mất mạng
  local url="$1" dest="$2" hdr="${3:-}" dir base
  dir="$(dirname "$dest")"; base="$(basename "$dest")"
  mkdir -p "$dir"
  local headers=()
  [[ -z "$hdr" ]] || headers=("--header=$hdr")
  if command -v aria2c >/dev/null 2>&1; then
    if aria2c -x8 -s8 -k1M -c --allow-overwrite=true --auto-file-renaming=false \
      --file-allocation=none --console-log-level=warn --summary-interval=10 \
      --connect-timeout=20 --timeout=60 --max-tries=3 --retry-wait=3 \
      "${headers[@]}" -d "$dir" -o "$base" "$url"; then
      return 0
    fi
    warn "aria2c lỗi, thử wget (tiếp tục phần đã tải) ..."
  fi
  if command -v wget >/dev/null 2>&1; then
    if wget --continue --timeout=60 --tries=3 --no-verbose \
      "${headers[@]}" -O "$dest" "$url"; then return 0; fi
    warn "wget lỗi, thử curl ..."
  fi
  headers=()
  [[ -z "$hdr" ]] || headers=(-H "$hdr")
  curl --fail --location --show-error --connect-timeout 20 --max-time 3600 \
    --retry 3 --retry-delay 3 -C - -o "$dest" "${headers[@]}" "$url"
}

model_valid() {
  [[ -f "$1" ]] || return 1
  local bytes
  bytes=$(stat -c '%s' "$1")
  (( bytes >= MODEL_MIN_BYTES )) || return 1
  # SHA256 mới là điều kiện xác minh đầy đủ, không coi kích thước 97% là "tải xong".
  if [[ -n "$MODEL_SHA256" ]]; then
    echo "$MODEL_SHA256  $1" | sha256sum -c --status || return 1
  elif [[ "${ALLOW_UNVERIFIED_MODEL:-0}" != "1" ]]; then
    return 1
  fi
  # Hash đúng vẫn cần là container safetensors hoàn chỉnh, không phải pointer/HTML.
  local -a validate_args=(--quiet)
  [[ "$1" != *.safetensors.part ]] || validate_args+=(--download-temp)
  "$PY" "$(checkpoint_helper)" validate "$1" "${validate_args[@]}"
}

stage_model() {
  step "Tải $MODEL_LABEL"
  [[ "$MODEL_FILE" == *.safetensors && "$MODEL_FILE" != */* && "$MODEL_FILE" != .* ]] \
    || die "MODEL_FILE phải là tên file .safetensors, không phải đường dẫn."
  [[ "$MODEL_MIN_BYTES" =~ ^[0-9]+$ ]] || die "MODEL_MIN_BYTES phải là số nguyên."
  [[ -z "$MODEL_SHA256" || "$MODEL_SHA256" =~ ^[a-fA-F0-9]{64}$ ]] || die "SHA256 không hợp lệ."
  [[ -n "$MODEL_SHA256" || "${ALLOW_UNVERIFIED_MODEL:-0}" == "1" ]] \
    || die "Thiếu SHA256: cấp MODEL_SHA256, hoặc cho phép bằng ALLOW_UNVERIFIED_MODEL=1 (không khuyến nghị)."
  mkdir -p "$MODEL_DIR"
  local dest="$MODEL_DIR/$MODEL_FILE" partial="$MODEL_DIR/$MODEL_FILE.part"

  if model_valid "$dest"; then
    ok "Model đã có và xác minh đạt: $dest"; return 0
  fi
  [[ ! -f "$dest" ]] || warn "File đã có nhưng kiểm tra không đạt — sẽ thay bằng bản tải đã xác minh."

  # Giữ .part + .aria2 khi ngắt mạng/ô Colab. Chỉ đổi tên sau khi SHA256 khớp,
  # nên Forge không bao giờ thấy checkpoint đang tải dở.
  local url host hdr
  for url in "${MODEL_URLS[@]}"; do
    host="$($PY -c 'from urllib.parse import urlsplit; import sys; print(urlsplit(sys.argv[1]).hostname or "nguồn tùy chỉnh")' "$url")"
    info "Tải từ $host (không in URL/token vào log) ..."
    hdr=""
    if [[ "$host" == "civitai.com" || "$host" == "civitai.red" ]]; then
      [[ -z "$CIVITAI_TOKEN" ]] || hdr="Authorization: Bearer $CIVITAI_TOKEN"
    fi
    if ! fetch "$url" "$partial" "$hdr"; then
      warn "Tải chưa xong — giữ $partial để tiếp tục khi chạy lại."
      continue
    fi
    info "Xác minh file tải về ..."
    if model_valid "$partial"; then
      mv -f "$partial" "$dest"
      rm -f -- "$partial.aria2"
      [[ -n "$MODEL_SHA256" ]] || warn "Đã cho phép bỏ qua SHA256; chỉ kiểm tra dung lượng."
      ok "Model sẵn sàng: $dest"; ls -lh "$dest"; return 0
    fi
    warn "File tải xong nhưng dung lượng/SHA256 sai — bỏ phần hỏng rồi thử nguồn khác."
    rm -f -- "$partial" "$partial.aria2"
  done
  die "Chưa tải được model. Phần tải dở (nếu có) được giữ lại. Kiểm tra mạng/token và chạy lại; hoặc cấp MODEL_URL + MODEL_SHA256."
}

# ------------------------------------------------------------------- config version
ensure_config_version() {
  # verify_version() chạy TRƯỚC prepare_environment()/WebUI. Nếu bộ cài tự tạo
  # config.json mà thiếu VERSION_UID, một bản cài mới cũng bị coi là bản cũ và
  # input("Press Enter...") sẽ EOF khi chạy nền. Đọc UID bằng AST, không import
  # launch_utils (vốn phụ thuộc torch), không hardcode UID và không bỏ qua guard.
  FORGE_LAUNCH_UTILS="$FORGE_DIR/modules/launch_utils.py" \
  CONFIG_JSON="$FORGE_DIR/config.json" $PY - <<'PYVERSION'
import ast
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

source = Path(os.environ["FORGE_LAUNCH_UTILS"])
path = Path(os.environ["CONFIG_JSON"])
try:
    tree = ast.parse(source.read_text(encoding="utf-8"))
except (OSError, SyntaxError) as exc:
    raise SystemExit(f"Không đọc được VERSION_UID của Forge: {source} ({type(exc).__name__}).")

uid = None
for node in tree.body:
    if isinstance(node, ast.AnnAssign):
        targets, value = [node.target], node.value
    elif isinstance(node, ast.Assign):
        targets, value = node.targets, node.value
    else:
        continue
    if any(isinstance(t, ast.Name) and t.id == "VERSION_UID" for t in targets):
        try:
            uid = ast.literal_eval(value)
        except (ValueError, TypeError):
            raise SystemExit("VERSION_UID của Forge không còn là hằng chuỗi; cần cập nhật bộ cài.")
if not isinstance(uid, str) or not uid:
    raise SystemExit("Không tìm thấy VERSION_UID hợp lệ trong mã Forge; không tự đoán phiên bản.")

exists = path.exists()
try:
    data = json.loads(path.read_text(encoding="utf-8")) if exists else {}
except (OSError, ValueError) as exc:
    raise SystemExit(f"config.json không đọc được; hãy sửa/backup file trước ({type(exc).__name__}).")
if not isinstance(data, dict):
    raise SystemExit("config.json phải là JSON object; không tự ghi đè file này.")
if data.get("VERSION_UID") == uid:
    print(f"   VERSION_UID={uid} — cấu hình Forge đã đúng phiên bản.")
    raise SystemExit(0)

# Chỉ tự khởi tạo/sửa cấu hình tối thiểu do bộ cài tạo. Cấu hình Forge cũ thật sự
# (UID khác hoặc có tùy chọn legacy khác) vẫn phải được người dùng backup/reset;
# không gắn nhãn phiên bản mới lên nó để lách cảnh báo breaking changes.
safe_keys = {"VERSION_UID", "sd_model_checkpoint", "clip_stop_at_last_layers"}
installer_only = all(k in safe_keys or k.startswith("tac_") for k in data)
if "VERSION_UID" in data or not installer_only:
    raise SystemExit(
        "Cấu hình Forge cũ/không do bộ cài tạo: cần sao lưu config.json và ui-config.json "
        "rồi khởi tạo lại cấu hình theo hướng dẫn colab/INSTALL.md. "
        "Không tự đổi VERSION_UID của cấu hình cũ; model/ảnh không bị đụng tới."
    )

path.parent.mkdir(parents=True, exist_ok=True)
if exists:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.wai-backup-{stamp}-{uuid.uuid4().hex[:8]}")
    shutil.copy2(path, backup)
    backup.chmod(0o600)
    print(f"   Backup cấu hình trước khi bổ sung UID: {backup}")
data["VERSION_UID"] = uid
# Cùng filesystem, ghi nguyên tử; không để lại config.json tải/ghi dở.
tmp = None
try:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.wai-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
finally:
    if tmp is not None:
        tmp.unlink(missing_ok=True)
print(f"   Đã khởi tạo VERSION_UID={uid}; giữ nguyên tagcomplete/checkpoint/CLIP.")
PYVERSION
}

# ------------------------------------------------------------------- extras
stage_extras() {
  step "Cắm kho prompt tiếng Việt vào Forge"
  [[ -d "$FORGE_DIR" ]] || die "Chạy stage 'forge' trước."
  [[ -f "$REPO_DIR/danbooru_e621.csv" ]] || die "Chạy stage 'repo' trước (thiếu kho prompt ở $REPO_DIR)."
  local source_file
  for source_file in colab/prompt_lib/editing.py colab/prompt_lib/workflow.py \
                     colab/extension/vi-prompt-builder/javascript/vi_prompt.js; do
    [[ -s "$REPO_DIR/$source_file" ]] || die "Repo thiếu $source_file. Cập nhật cùng nhánh trước; chưa thay đổi extension đang có."
  done
  ensure_config_version

  # 1) upscaler cho hires fix — Forge Neo đặt tên scaler THEO TÊN FILE, nên file
  #    RealESRGAN_x4plus_anime_6B.pth sẽ hiện ra đúng là "RealESRGAN_x4plus_anime_6B".
  mkdir -p "$UPSCALER_DIR"
  if [[ ! -f "$UPSCALER_DIR/RealESRGAN_x4plus_anime_6B.pth" ]]; then
    info "Tải upscaler anime 6B (18 MB)"
    local up="$UPSCALER_DIR/RealESRGAN_x4plus_anime_6B.pth"
    if fetch "$UPSCALER_URL" "$up.part" && [[ $(stat -c '%s' "$up.part") -ge 17000000 ]]; then
      mv -f "$up.part" "$up"; rm -f -- "$up.part.aria2"
      ok "Upscaler: RealESRGAN_x4plus_anime_6B"
    else
      warn "Tải upscaler chưa xong (Forge vẫn chạy; bộ dựng prompt sẽ chọn scaler đang có)."
    fi
  else
    ok "Upscaler đã có sẵn."
  fi

  # 2) sinh bộ file cho tagcomplete từ kho prompt
  info "Sinh tag hệ thống + bản dịch gộp"
  (cd "$REPO_DIR" && $PY colab/make_tagcomplete_assets.py) \
    || die "make_tagcomplete_assets.py chạy lỗi."

  # 3) cài tagcomplete
  local ext="$FORGE_DIR/extensions"
  mkdir -p "$ext"
  if [[ ! -d "$ext/a1111-sd-webui-tagcomplete" ]]; then
    info "Cài sd-webui-tagcomplete"
    git clone --depth 1 "$TAC_REPO" "$ext/a1111-sd-webui-tagcomplete" \
      || die "Không clone được tagcomplete."
  fi
  local tags_dir="$ext/a1111-sd-webui-tagcomplete/tags"
  mkdir -p "$tags_dir"
  info "Chép kho prompt vào $tags_dir"
  cp -f "$REPO_DIR/danbooru_e621.csv"                                  "$tags_dir/"
  cp -f "$REPO_DIR/colab/assets/wai-illustrious-system-tags.csv"       "$tags_dir/"
  cp -f "$REPO_DIR/colab/assets/danbooru_e621_vi_translation_wai.csv"  "$tags_dir/"
  find "$tags_dir" -maxdepth 1 -type f -printf '   %f (%s byte)\n'

  # 4) cấu hình sẵn tagcomplete (khoá lấy từ scripts/tag_autocomplete_helper.py)
  info "Ghi cấu hình tagcomplete"
  TAC_TAG_FILE="danbooru_e621.csv" \
  TAC_EXTRA_FILE="wai-illustrious-system-tags.csv" \
  TAC_TRANS_FILE="danbooru_e621_vi_translation_wai.csv" \
  CONFIG_JSON="$FORGE_DIR/config.json" $PY - <<'PYCFG'
import json, os
path = os.environ["CONFIG_JSON"]
data = {}
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"config.json không đọc được; hãy sửa/backup file trước: {exc}")
if not isinstance(data, dict):
    raise SystemExit("config.json phải là JSON object.")
data.update({
    # tag file chính: bản tiếng Anh có "_" (tagcomplete tự thay "_" bằng khoảng
    # trắng khi chèn, và đã có sẵn danh sách loại trừ emoticon ^_^, o_o, |_|...)
    "tac_tagFile": os.environ["TAC_TAG_FILE"],
    "tac_active": True,
    "tac_activeIn.txt2img": True,
    "tac_activeIn.img2img": True,
    "tac_activeIn.negativePrompts": True,
    "tac_maxResults": 10,
    "tac_slidingPopup": True,
    "tac_replaceUnderscores": True,
    "tac_appendComma": True,
    "tac_alias.searchByAlias": True,
    "tac_frequencySort": True,
    "tac_artistAtTrigger": True,
    # tag hệ thống Illustrious/WAI (rating_*, masterpiece, newest, very awa...)
    "tac_extra.extraFile": os.environ["TAC_EXTRA_FILE"],
    "tac_extra.addMode": "Insert before",
    # bản dịch tiếng Việt: 2 cột, cho phép tìm bằng tiếng Việt và hiện nghĩa dưới prompt
    "tac_translation.translationFile": os.environ["TAC_TRANS_FILE"],
    "tac_translation.oldFormat": False,
    "tac_translation.searchByTranslation": True,
    "tac_translation.liveTranslation": True,
    # CLIP stop at last layers = 2 (khuyến nghị cho họ Illustrious)
    "clip_stop_at_last_layers": 2,
})
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("   đã ghi", path, "với", len(data), "khoá")
PYCFG

  # 5) styles.csv: 4 mức phân loại bấm được ngay trong Forge
  if [[ -f "$REPO_DIR/colab/assets/styles.csv" ]]; then
    if [[ -f "$FORGE_DIR/styles.csv" ]]; then
      info "styles.csv đã có — nối thêm style WAI chưa có"
      $PY - "$FORGE_DIR/styles.csv" "$REPO_DIR/colab/assets/styles.csv" <<'PYSTY'
import csv, sys
dst, src = sys.argv[1], sys.argv[2]
rows = list(csv.reader(open(dst, newline='', encoding='utf-8')))
have = {r[0] for r in rows if r}
new = [r for r in csv.reader(open(src, newline='', encoding='utf-8')) if r and r[0] not in have]
if new:
    with open(dst, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f, lineterminator='\n').writerows(new[1:] if new[0][0] == 'name' else new)
print('   đã thêm', len([r for r in new if r[0] != 'name']), 'style')
PYSTY
    else
      cp -f "$REPO_DIR/colab/assets/styles.csv" "$FORGE_DIR/styles.csv"
      ok "Đã tạo styles.csv (4 style WAI v17)."
    fi
  fi

  # 6) extension "Prompt VN"
  info "Cài extension Prompt VN"
  rm -rf "$ext/vi-prompt-builder"
  cp -r "$REPO_DIR/colab/extension/vi-prompt-builder" "$ext/vi-prompt-builder"
  # trỏ extension tới repo để nó tự tìm prompt_lib và các file CSV
  echo "$REPO_DIR" > "$ext/vi-prompt-builder/.repo_root"
  ok "Đã cài extension (tab 'Prompt VN' sẽ hiện trong Forge)."
}

# ------------------------------------------------------------------- launch
launch_args() {
  # Forge Neo chỉ có --ckpt-dirs (không có --models-dir/--data-dir).
  # shlex.quote bảo toàn đường dẫn có khoảng trắng khi launch.py đọc biến môi trường.
  local args="--listen --port $PORT --api --expandable-segments"
  local model_path
  model_path="$($PY -c 'import shlex,sys; print(shlex.quote(sys.argv[1]))' "$MODEL_DIR")"
  args="$args --ckpt-dirs $model_path"
  [[ -z "$VRAM_FLAG" ]] || args="$args $VRAM_FLAG"
  [[ "$TUNNEL" != "share" ]] || args="$args --share"
  [[ -z "$EXTRA_FORGE_ARGS" ]] || args="$args $EXTRA_FORGE_ARGS"
  echo "$args"
}

owned_process() { # owned_process <pid file> <fragment>; không đụng process của người khác
  [[ -f "$1" ]] || return 1
  local pid
  pid=$(cat "$1")
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null || return 1
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  tr '\0' ' ' < "/proc/$pid/cmdline" | grep -Fq -- "$2"
}

stop_owned() {
  local pid_file="$1" fragment="$2" pid
  if owned_process "$pid_file" "$fragment"; then
    pid=$(cat "$pid_file")
    info "Dừng process của bộ cài: $pid"
    kill "$pid"
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f -- "$pid_file"
}

stage_stop() {
  stop_owned "$FORGE_PID_FILE" "$FORGE_DIR/launch.py"
  stop_owned "$TUNNEL_PID_FILE" 'cloudflared tunnel'
}

start_cloudflared() {
  [[ "$TUNNEL" == "cloudflared" ]] || return 0
  local bin="$RUNTIME_DIR/bin/cloudflared" url pid
  mkdir -p "$(dirname "$bin")"
  if [[ ! -x "$bin" ]]; then
    info "Tải cloudflared"
    fetch https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 "$bin.part" \
      || die "Không tải được cloudflared. Thử TUNNEL=share."
    mv -f "$bin.part" "$bin"; rm -f -- "$bin.part.aria2"; chmod +x "$bin"
  fi
  if ! owned_process "$TUNNEL_PID_FILE" 'cloudflared tunnel'; then
    nohup "$bin" tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate \
      > "$TUNNEL_LOG" 2>&1 < /dev/null &
    pid=$!; echo "$pid" > "$TUNNEL_PID_FILE"
  fi
  info "Chờ link cloudflared ..."
  for _ in {1..60}; do
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    if [[ -n "$url" ]]; then ok "Link public: $url"; return 0; fi
    owned_process "$TUNNEL_PID_FILE" 'cloudflared tunnel' || die "Tunnel đã dừng. Xem $TUNNEL_LOG; hoặc đổi TUNNEL=share."
    sleep 2
  done
  die "Chưa có link tunnel sau 2 phút. Xem $TUNNEL_LOG hoặc đổi TUNNEL=share."
}

prepare_launch() {
  mkdir -p "$RUNTIME_DIR"
  cd "$FORGE_DIR" || die "thiếu $FORGE_DIR"
  [[ -x "$FORGE_DIR/venv/bin/python" ]] || die "Chưa có venv của Forge. Chạy stage forge trước."
  ensure_config_version # cũng sửa lần cài v1.0.0 chỉ chạy lại stage launch
  # shellcheck disable=SC1090 # file do stage torch tạo trong runtime của người dùng
  [[ ! -f "$TORCH_ENV_FILE" ]] || source "$TORCH_ENV_FILE"
  export GRADIO_PACKAGE="gradio==4.40.0 gradio_rangeslider==0.0.8"
  export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD="true"
  COMMANDLINE_ARGS="$(launch_args)"
  export COMMANDLINE_ARGS VI_PROMPT_ROOT="$REPO_DIR"
  # Neo còn lưu model RIÊNG theo preset. Chỉ ghi sd_model_checkpoint là chưa đủ:
  # forge_checkpoint_xl mặc định None sẽ làm dropdown trống khi on_preset_change chạy.
  # Kiểm header + hash, alias có quản lý, backup config và đặt preset SDXL nhất quán.
  configure_checkpoint
  # Forge/extension không cần giữ credential dùng để clone/tải model.
  unset GITHUB_TOKEN CIVITAI_TOKEN GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
  info "Forge sẽ nghe trên 0.0.0.0:$PORT; model dir: $MODEL_DIR"
}

stage_launch() {
  step "Khởi động Forge Neo"
  prepare_launch
  start_cloudflared
  info "Lần đầu Forge còn cài dependencies — xem log trực tiếp ở dưới."
  # Dùng đường dẫn tuyệt đối để PID có thể được kiểm tra trước khi dừng/khởi động lại.
  echo "$$" > "$FORGE_PID_FILE"
  exec "$FORGE_DIR/venv/bin/python" "$FORGE_DIR/launch.py"
}

stage_launch_bg() {
  step "Khởi động Forge Neo (chạy nền)"
  if curl -fsS -m 3 "http://127.0.0.1:$PORT/sdapi/v1/sd-models" >/dev/null 2>&1; then
    die "Cổng $PORT đã có API. Không tạo process thứ hai; dùng bộ cài install.sh để tiếp tục/khởi động lại."
  fi
  if owned_process "$FORGE_PID_FILE" "$FORGE_DIR/launch.py"; then
    info "Forge đang khởi động — chờ process hiện có, không chạy trùng."
  else
    prepare_launch
    nohup "$FORGE_DIR/venv/bin/python" "$FORGE_DIR/launch.py" > "$FORGE_LOG" 2>&1 < /dev/null &
    echo "$!" > "$FORGE_PID_FILE"
  fi
  local deadline=$(( SECONDS + LAUNCH_TIMEOUT )) ready=0 pub
  info "Chờ API Forge (log: $FORGE_LOG) ..."
  while (( SECONDS < deadline )); do
    if curl -fsS -m 5 "http://127.0.0.1:$PORT/sdapi/v1/sd-models" >/dev/null 2>&1; then ready=1; break; fi
    if ! owned_process "$FORGE_PID_FILE" "$FORGE_DIR/launch.py"; then
      tail -40 "$FORGE_LOG" >&2 || true
      die "Forge đã dừng — xem log ở trên."
    fi
    sleep 5
  done
  [[ "$ready" == "1" ]] || die "API chưa sẵn sàng sau ${LAUNCH_TIMEOUT}s. Xem $FORGE_LOG rồi chạy lại (không chạy trùng process)."
  start_cloudflared
  if [[ "$TUNNEL" == "share" ]]; then
    # Có API chưa chắc Gradio share đã tạo link. Chờ thêm tối đa 60s.
    for _ in {1..30}; do
      pub=$(grep -oE 'https://[a-z0-9.-]+\.gradio\.live' "$FORGE_LOG" | head -1 || true)
      if [[ -n "$pub" ]]; then ok "Link public: $pub"; break; fi
      sleep 2
    done
    [[ -n "$pub" ]] || die "Forge sẵn sàng nhưng chưa có Gradio share link. Thử TUNNEL=cloudflared."
  fi
  ok "API Forge đã phản hồi ở cổng $PORT."
}

# ------------------------------------------------------------------- all
stage_all() { stage_gpu; stage_repo; stage_forge; stage_torch; stage_model; stage_extras; }

main() {
case "${1:-all}" in
  gpu)        stage_gpu ;;
  repo)       stage_repo ;;
  forge)      stage_forge ;;
  torch)      stage_torch ;;
  model)      stage_model ;;
  extras)     stage_extras ;;
  launch)     stage_launch ;;
  launch-bg)  stage_launch_bg ;;
  stop)       stage_stop ;;
  all)        stage_all ;;
  *)          die "stage không hợp lệ: ${1:-} (chọn: gpu repo forge torch model extras launch launch-bg stop all)" ;;
esac
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
