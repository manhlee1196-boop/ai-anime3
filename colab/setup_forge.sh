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
set -uo pipefail

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

MODEL_DIR="${MODEL_DIR:-$FORGE_DIR/models/Stable-diffusion}"
MODEL_FILE="${MODEL_FILE:-waiIllustriousSDXL_v170.safetensors}"
MODEL_SHA256="${MODEL_SHA256:-f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04}"
CIVITAI_VERSION_ID="${CIVITAI_VERSION_ID:-2883731}"
CIVITAI_TOKEN="${CIVITAI_TOKEN:-}"
# Mirror HuggingFace tải không cần token; đã đối chiếu SHA256 với bản Civitai gốc.
MODEL_URLS=(
  "https://huggingface.co/LyliaEngine/waiIllustriousSDXL_v170/resolve/main/waiIllustriousSDXL_v170.safetensors"
  "https://huggingface.co/Coercer/Modified_VeryFast_Models_DMD2/resolve/main/Orig_Models_Pruned/waiIllustriousSDXL_v170.safetensors"
)
UPSCALER_DIR="${UPSCALER_DIR:-$FORGE_DIR/models/ESRGAN}"
UPSCALER_URL="${UPSCALER_URL:-https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth}"
TAC_REPO="${TAC_REPO:-https://github.com/DominikDoom/a1111-sd-webui-tagcomplete}"
PY="${PY:-python3}"

# ------------------------------------------------------------------- tiện ích
c()   { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info(){ c '1;36' "▶ $*"; }
ok()  { c '1;32' "✔ $*"; }
warn(){ c '1;33' "⚠ $*"; }
die() { c '1;31' "✖ $*"; exit 1; }
step(){ echo; c '1;35' "═══ $* ═══"; }

need() { command -v "$1" >/dev/null 2>&1 || die "thiếu lệnh '$1' — hãy cài trước."; }

# ------------------------------------------------------------------- gpu
stage_gpu() {
  step "Kiểm tra môi trường Colab"
  command -v nvidia-smi >/dev/null 2>&1 || die "Không thấy nvidia-smi: hãy bật GPU (Runtime > Change runtime type > T4/L4/A100)."
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
  echo
  # phiên bản CUDA mà driver hỗ trợ -> quyết định chọn wheel torch nào
  CUDA_VER="$(nvidia-smi | grep -oE 'CUDA Version: [0-9.]+' | grep -oE '[0-9]+\.[0-9]+' | head -1)"
  CUDA_MAJOR="${CUDA_VER%%.*}"
  echo "Driver hỗ trợ CUDA: ${CUDA_VER:-không rõ}"
  if [[ "${CUDA_MAJOR:-0}" -ge 13 ]]; then
    echo "TORCH_INDEX=cu130" > /content/.wai_torch_env
  else
    echo "TORCH_INDEX=cu128" > /content/.wai_torch_env
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
  step "Lấy kho prompt (repo này)"
  if [[ -f "$REPO_DIR/danbooru_e621.csv" ]]; then
    ok "Đã có sẵn $REPO_DIR — bỏ qua clone."
    return 0
  fi
  need git
  local url="$REPO_URL"
  if [[ -n "$GITHUB_TOKEN" ]]; then
    url="${REPO_URL/https:\/\/github.com\//https://oauth2:${GITHUB_TOKEN}@github.com/}"
    info "Dùng token GitHub để clone (repo private)."
  fi
  # thử nhánh đã cấu hình, rồi main, rồi master — vì nhánh làm việc có thể đã được gộp
  local branch cloned=1
  for branch in "$REPO_BRANCH" main master; do
    info "Thử clone nhánh '$branch' ..."
    if git clone --depth 1 --branch "$branch" "$url" "$REPO_DIR" 2>/dev/null; then
      cloned=0; ok "Đã clone nhánh '$branch' vào $REPO_DIR"; break
    fi
    rm -rf "$REPO_DIR"
  done
  [[ $cloned -eq 0 ]] || die "Không clone được $REPO_URL. Nếu repo để private, hãy đặt GITHUB_TOKEN ở ô Cấu hình, hoặc chép 4 file CSV vào $REPO_DIR thủ công."
  [[ -f "$REPO_DIR/danbooru_e621.csv" ]] || die "Clone xong nhưng thiếu danbooru_e621.csv trong $REPO_DIR."
  ls -lh "$REPO_DIR"/*.csv | awk '{print "   ", $9, $5}'
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

  info "Cài uv (trình quản lý gói nhanh)"
  $PY -m pip install --quiet --upgrade uv 2>/dev/null \
    || pip install --quiet --upgrade uv --break-system-packages 2>/dev/null \
    || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
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
  source /content/.wai_torch_env 2>/dev/null || TORCH_INDEX=cu130

  # Danh sách ứng viên: đúng bản Forge Neo khuyến nghị trước, rồi lùi dần.
  local candidates=()
  case "$TORCH_INDEX" in
    cu130) candidates=("cu130|torch==2.13.0+cu130 torchvision==0.28.0+cu130") ;;
    *)     candidates=("cu128|torch torchvision") ;;
  esac
  candidates+=("cu128|torch torchvision" "cu126|torch torchvision")

  local check='import torch,sys
print("torch", torch.__version__)
sys.exit(0 if torch.cuda.is_available() else 3)'

  local idx pkgs
  for entry in "${candidates[@]}"; do
    idx="${entry%%|*}"; pkgs="${entry#*|}"
    info "Thử $idx: pip install $pkgs"
    "$venvpy" -m pip install --quiet $pkgs --index-url "https://download.pytorch.org/whl/$idx" \
      || { warn "cài $idx thất bại, thử bản khác"; continue; }
    if "$venvpy" -c "$check"; then
      ok "PyTorch $idx dùng được với GPU này."
      # ghi lại để launch.py không cài đè bản khác
      cat > /content/.wai_torch_env <<EOF
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

# ------------------------------------------------------------------- model
fetch() {  # fetch <url> <đích> [header] — thử aria2c -> wget -> curl
  local url="$1" dest="$2" hdr="${3:-}" dir base
  dir="$(dirname "$dest")"; base="$(basename "$dest")"
  mkdir -p "$dir"
  if command -v aria2c >/dev/null 2>&1; then
    aria2c -x16 -s16 -k1M -c --file-allocation=none --console-log-level=warn \
      ${hdr:+--header="$hdr"} -d "$dir" -o "$base" "$url" && return 0
    warn "aria2c lỗi, thử wget ..."
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -c -O "$dest" ${hdr:+--header="$hdr"} "$url" && return 0
    warn "wget lỗi, thử curl ..."
  fi
  curl -L -C - -o "$dest" ${hdr:+-H "$hdr"} "$url"
}

stage_model() {
  step "Tải WAI-illustrious-SDXL v17.0 (6,5 GB)"
  mkdir -p "$MODEL_DIR"
  local dest="$MODEL_DIR/$MODEL_FILE"

  if [[ -f "$dest" ]] && du -b "$dest" | awk '{exit !($1>6000000000)}'; then
    info "File đã có, kiểm tra SHA256 ..."
    if echo "$MODEL_SHA256  $dest" | sha256sum -c --status 2>/dev/null; then
      ok "Model sẵn sàng: $dest"; return 0
    fi
    warn "SHA256 sai -> tải lại."
    rm -f "$dest"
  fi

  # gộp danh sách: mirror HF + Civitai (nếu có token)
  local urls=("${MODEL_URLS[@]}")
  [[ -n "$CIVITAI_TOKEN" ]] && urls+=("https://civitai.com/api/download/models/$CIVITAI_VERSION_ID")

  local url
  for url in "${urls[@]}"; do
    info "Thử tải: ${url:0:78}..."
    local hdr=""
    [[ "$url" == *civitai.com* ]] && hdr="Authorization: Bearer $CIVITAI_TOKEN"
    fetch "$url" "$dest" "$hdr" || { warn "tải lỗi, thử nguồn khác"; continue; }
    info "Đang kiểm SHA256 (mất ~20 giây) ..."
    if echo "$MODEL_SHA256  $dest" | sha256sum -c --status 2>/dev/null; then
      ok "Tải xong và SHA256 khớp: $MODEL_SHA256"; ls -lh "$dest"; return 0
    fi
    warn "SHA256 KHÔNG khớp (file hỏng hoặc mirror khác bản) -> thử nguồn khác."
    rm -f "$dest"
  done
  die "Không tải được model từ nguồn nào. Đặt MODEL_URL thủ công, hoặc chép file vào $MODEL_DIR (Colab cho phép kéo-thả vào khung Files)."
}

# ------------------------------------------------------------------- extras
stage_extras() {
  step "Cắm kho prompt tiếng Việt vào Forge"
  [[ -d "$FORGE_DIR" ]] || die "Chạy stage 'forge' trước."
  [[ -f "$REPO_DIR/danbooru_e621.csv" ]] || die "Chạy stage 'repo' trước (thiếu kho prompt ở $REPO_DIR)."

  # 1) upscaler cho hires fix — Forge Neo đặt tên scaler THEO TÊN FILE, nên file
  #    RealESRGAN_x4plus_anime_6B.pth sẽ hiện ra đúng là "RealESRGAN_x4plus_anime_6B".
  mkdir -p "$UPSCALER_DIR"
  if [[ ! -f "$UPSCALER_DIR/RealESRGAN_x4plus_anime_6B.pth" ]]; then
    info "Tải upscaler anime 6B (18 MB)"
    fetch "$UPSCALER_URL" "$UPSCALER_DIR/RealESRGAN_x4plus_anime_6B.pth" \
      && ok "Upscaler: RealESRGAN_x4plus_anime_6B" || warn "tải upscaler lỗi (Forge vẫn chạy, hires fix sẽ dùng Latent)."
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
  ls -lh "$tags_dir" | awk 'NR>1{print "   ", $9, $5}'

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
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        data = {}
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
print('   đã thêm', max(len(new) - 1, 0), 'style')
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
  local args="--listen --port $PORT --api --expandable-segments"
  [[ -n "$VRAM_FLAG" ]] && args="$args $VRAM_FLAG"
  [[ "$TUNNEL" == "share" ]] && args="$args --share"
  echo "$args"
}

start_cloudflared() {
  [[ "$TUNNEL" == "cloudflared" ]] || return 0
  command -v cloudflared >/dev/null 2>&1 || {
    info "Tải cloudflared"
    wget -q -O /usr/local/bin/cloudflared \
      https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
      && chmod +x /usr/local/bin/cloudflared
  }
  nohup cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate \
    > /content/cloudflared.log 2>&1 &
  info "Đang chờ link cloudflared ..."
  for _ in $(seq 1 60); do
    local url; url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /content/cloudflared.log | head -1)
    [[ -n "$url" ]] && { echo; ok "Link public: $url"; return 0; }
    sleep 2
  done
  warn "Chưa thấy link cloudflared; xem /content/cloudflared.log"
}

stage_launch() {
  step "Khởi động Forge Neo"
  cd "$FORGE_DIR" || die "thiếu $FORGE_DIR"
  source /content/.wai_torch_env 2>/dev/null || true
  # launch.py tự cộng COMMANDLINE_ARGS vào sys.argv, nên KHÔNG truyền lại ở đây (sẽ bị lặp)
  export COMMANDLINE_ARGS VI_PROMPT_ROOT
  COMMANDLINE_ARGS="$(launch_args)"
  VI_PROMPT_ROOT="$REPO_DIR"
  echo "COMMANDLINE_ARGS=$COMMANDLINE_ARGS"
  start_cloudflared
  info "Forge đang cài phần còn lại rồi khởi động (lần đầu 3–8 phút) ..."
  exec "$FORGE_DIR/venv/bin/python" launch.py
}

stage_launch_bg() {
  step "Khởi động Forge Neo (chạy nền)"
  cd "$FORGE_DIR" || die "thiếu $FORGE_DIR"
  source /content/.wai_torch_env 2>/dev/null || true
  COMMANDLINE_ARGS="$(launch_args)"
  export COMMANDLINE_ARGS VI_PROMPT_ROOT="$REPO_DIR"
  start_cloudflared
  nohup "$FORGE_DIR/venv/bin/python" launch.py > /content/forge.log 2>&1 &
  info "Đang chờ Forge sẵn sàng (log: /content/forge.log) ..."
  for _ in $(seq 1 240); do
    if grep -q "Running on public URL" /content/forge.log 2>/dev/null; then
      echo; ok "Link public: $(grep -oE 'https://[a-z0-9.-]+\.gradio\.live' /content/forge.log | head -1)"
      return 0
    fi
    if grep -qE "Startup time|To create a public link" /content/forge.log 2>/dev/null; then
      grep -oE 'https://[a-z0-9.-]+\.gradio\.live' /content/forge.log | head -1 | sed 's/^/   /'
    fi
    if ! kill -0 $! 2>/dev/null; then
      tail -25 /content/forge.log
      die "Forge đã dừng — xem log ở trên."
    fi
    sleep 5
  done
  warn "Chờ quá 20 phút. Xem /content/forge.log"
}

# ------------------------------------------------------------------- all
stage_all() { stage_gpu; stage_repo; stage_forge; stage_torch; stage_model; stage_extras; }

case "${1:-all}" in
  gpu)        stage_gpu ;;
  repo)       stage_repo ;;
  forge)      stage_forge ;;
  torch)      stage_torch ;;
  model)      stage_model ;;
  extras)     stage_extras ;;
  launch)     stage_launch ;;
  launch-bg)  stage_launch_bg ;;
  all)        stage_all ;;
  *)          die "stage không hợp lệ: ${1:-} (chọn: gpu repo forge torch model extras launch launch-bg all)" ;;
esac
