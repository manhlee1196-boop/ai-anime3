#!/usr/bin/env bash
# Bộ cài Colab một lệnh: WAI-Illustrious v17 + Forge Neo + kho prompt tiếng Việt.
# Mặc định: FP16 gốc, lưu trong /content; không mount Drive, không cần token GitHub.
# Xem hướng dẫn: colab/INSTALL.md. Notebook một ô: colab/WAI_v17_1click.ipynb.
set -Eeuo pipefail

INSTALLER_VERSION="1.0.2"
DEFAULT_STAGES=(preflight repo forge torch model extras launch verify)
STATE_DIR="${STATE_DIR:-/content/.wai_state}"
LOG="${WAI_LOG:-/content/wai_install.log}"
RUNTIME_DIR="${WAI_RUNTIME_DIR:-/content}"
PY_BIN="${PY:-python3}"
CONFIG_KEYS=(REPO_URL REPO_BRANCH REPO_DIR FORGE_DIR FORGE_REPO FORGE_BRANCH
             MODEL_ID MODEL_DIR PORT TUNNEL VRAM_FLAG EXTRA_FORGE_ARGS CUDA_INDEX)
# Nhớ cấu hình đã chọn ở lần trước, nhưng biến môi trường/cờ lần này luôn thắng.
# File JSON chỉ chứa cấu hình công khai, không lưu token hoặc URL tải riêng.
declare -A ENV_GIVEN=()
for key in "${CONFIG_KEYS[@]}"; do
  [[ ! -v "$key" ]] || ENV_GIVEN[$key]=1
done
REPO_URL="${REPO_URL:-https://github.com/manhlee1196-boop/ai-anime3}"
REPO_BRANCH="${REPO_BRANCH:-arena/88f01d31-ai-anime3}"
REPO_DIR="${REPO_DIR:-/content/ai-anime3}"
FORGE_DIR="${FORGE_DIR:-/content/sd-webui-forge-neo}"
FORGE_REPO="${FORGE_REPO:-https://github.com/Haoming02/sd-webui-forge-classic}"
FORGE_BRANCH="${FORGE_BRANCH:-neo}"
MODEL_ID="${MODEL_ID:-fp16}"
MODEL_DIR="${MODEL_DIR:-/content/models}"
MODEL_URL_OVERRIDE="${MODEL_URL:-}"
MODEL_FILE_OVERRIDE="${MODEL_FILE:-}"
MODEL_SHA_OVERRIDE="${MODEL_SHA256:-}"
MODEL_MIN_OVERRIDE="${MODEL_MIN_BYTES:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
CIVITAI_TOKEN="${CIVITAI_TOKEN:-}"
CIVITAI_API_BASE="${CIVITAI_API_BASE:-https://civitai.com/api/v1}"
PORT="${PORT:-7860}"
TUNNEL="${TUNNEL:-cloudflared}"
VRAM_FLAG="${VRAM_FLAG:-}"
EXTRA_FORGE_ARGS="${EXTRA_FORGE_ARGS:-}"
CUDA_INDEX="${CUDA_INDEX:-auto}"
CUDA_PICK="cu130"
ONLY_STAGES="${ONLY_STAGES:-}"
SKIP_STAGES="${SKIP_STAGES:-}"
WAI_NO_FALLBACK="${WAI_NO_FALLBACK:-1}"
DO_LAUNCH=1; FORCE=0; RESTART=0; SMOKE_TEST=0; MODE=install
CURRENT_STAGE=""; SETUP=""; SPEC_READY=0
MODEL_FILE=""; MODEL_SHA256=""; MODEL_LABEL=""; MODEL_MIN_BYTES=0; MODEL_URLS_STR=""
CIVITAI_VERSION_ID=""; GPU_NAME=""; DRIVER=""; GPU_VRAM_MB=0
VERIFY_FAIL=0; HALT_COUNT=0

info() { printf '▶ %s\n' "$*"; }
ok()   { printf '✔ %s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*"; }
bad()  { printf '✖ %s\n' "$*" >&2; }
step() { printf '\n═══ %s ═══\n' "$*"; }
die()  { bad "$*"; printf 'Log: %s\n' "$LOG" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
in_list() { local item; for item in ${1//,/ }; do [[ "$item" != "$2" ]] || return 0; done; return 1; }
selected() {
  [[ -z "$ONLY_STAGES" ]] || in_list "$ONLY_STAGES" "$1" || return 1
  [[ -z "$SKIP_STAGES" ]] || ! in_list "$SKIP_STAGES" "$1" || return 1
  [[ "$1" != launch || "$DO_LAUNCH" == 1 ]]
}
problem() {
  if [[ "$MODE" == install ]]; then die "$1"; fi
  bad "$1"; HALT_COUNT=$((HALT_COUNT + 1))
}
on_error() {
  local rc="$1" line="$2"
  trap - ERR
  [[ -z "$CURRENT_STAGE" ]] || rm -f -- "$STATE_DIR/$CURRENT_STAGE.ok"
  bad "Bước ${CURRENT_STAGE:-khởi tạo} lỗi (dòng $line, mã $rc). Không đánh dấu hoàn tất."
  printf 'Chạy lại cùng lệnh để tiếp tục; chẩn đoán: bash /content/install.sh --doctor\nLog: %s\n' "$LOG" >&2
  exit "$rc"
}
trap 'on_error "$?" "$LINENO"' ERR

usage() {
  cat <<EOF
BỘ CÀI WAI-Illustrious v17 + Forge Neo + kho prompt tiếng Việt

  bash install.sh --model fp16     # bản gốc FP16 pruned, ~6,5 GB (khuyến nghị)
  bash install.sh --model fp8      # FP8 e4m3, ~4,07 GB (thử nghiệm)
  bash install.sh --model int8     # INT8 convrot, ~4,39 GB (thử nghiệm)
  bash install.sh --model hswq     # HSWQ turbo, ~4,43 GB (thử nghiệm; CFG 1, steps 10)

  --model ID             fp16 | fp8 | int8 | hswq | custom
  --model-dir ĐƯỜNG_DẪN  nơi lưu model (mặc định /content/models)
  --model-url URLS        ghi đè nguồn tải; nhiều URL cách nhau bằng khoảng trắng
  --model-file TÊN        tên .safetensors; cần khi dùng --model custom
  --model-sha SHA256      SHA256 64 ký tự hex; cần khi dùng --model custom
  --repo URL             repo chứa kho prompt (mặc định ai-anime3)
  --branch NHÁNH         nhánh repo (mặc định $REPO_BRANCH)
  --forge-dir ĐƯỜNG_DẪN  nơi cài Forge (mặc định /content/sd-webui-forge-neo)
  --port SỐ              cổng Forge (mặc định 7860)
  --tunnel LOẠI          cloudflared | share | none
  --cuda IDX             auto | cu130 | cu128 | cu126
  --vram-flag CỜ         ví dụ "--lowvram"
  --forge-args CỜ        cờ Neo bổ sung, đặt trong ngoặc kép
  --only DS              chỉ chạy stage trong DS, phân cách dấu phẩy; buộc chạy lại
  --skip DS              bỏ qua stage trong DS
  --no-launch            chỉ cài, chưa mở Forge
  --restart              dừng/khởi động lại process do bộ cài quản lý
  --force                chạy lại các stage, không xoá model đã xác minh
  --fallback-fp16        cho phép lùi về FP16 khi không lấy được metadata Civitai
  --no-fallback          giữ nguyên biến thể đã chọn (mặc định)
  --print-models         xem catalog, không tải/cài gì
  --list-stages          xem thứ tự stage
  --status              xem trạng thái và link, không cài gì
  --doctor              kiểm tra/gợi ý sửa, không cài gì; exit 1 nếu có lỗi
  --diagnostics         in chẩn đoán checkpoint/API (chỉ đọc, không lộ token)
  --smoke-test          verify sinh 1 ảnh thử 256×256/1 step; có dùng GPU
  --clean               chỉ xoá marker .ok, giữ model, ảnh, cấu hình và repo
  --version             phiên bản bộ cài
  --help                hướng dẫn này

Stage: ${DEFAULT_STAGES[*]}
Ví dụ sửa: bash install.sh --only model,extras
Token (nếu cần) truyền qua GITHUB_TOKEN/CIVITAI_TOKEN hoặc Colab Secrets,
KHÔNG điền token vào lệnh/URL/notebook lưu công khai.
EOF
}

load_saved_settings() {
  [[ -f "$STATE_DIR/settings.json" ]] || return 0
  local key value
  while IFS= read -r -d '' key && IFS= read -r -d '' value; do
    [[ ${ENV_GIVEN[$key]:-0} == 1 ]] || printf -v "$key" '%s' "$value"
  done < <("$PY_BIN" - "$STATE_DIR/settings.json" "${CONFIG_KEYS[@]}" <<'PYSET'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError("not object")
except (OSError, ValueError):
    sys.exit(0)
for key in sys.argv[2:]:
    value = data.get(key)
    if isinstance(value, (str, int)) and "\0" not in str(value) and "\n" not in str(value):
        sys.stdout.write(f"{key}\0{value}\0")
PYSET
  )
  return 0
}
parse_args() {
  while (( $# )); do
    case "$1" in
      --model|--model-dir|--model-url|--model-file|--model-sha|--repo|--branch|--forge-dir|--port|--tunnel|--cuda|--vram-flag|--forge-args|--only|--skip)
        if (( $# < 2 )) || [[ "$2" == --* && "$1" != --vram-flag && "$1" != --forge-args ]]; then
          bad "Thiếu giá trị cho $1"; exit 2
        fi
        case "$1" in
          --model) MODEL_ID="$2" ;; --model-dir) MODEL_DIR="$2" ;;
          --model-url) MODEL_URL_OVERRIDE="$2" ;; --model-file) MODEL_FILE_OVERRIDE="$2" ;;
          --model-sha) MODEL_SHA_OVERRIDE="$2" ;; --repo) REPO_URL="$2" ;;
          --branch) REPO_BRANCH="$2" ;; --forge-dir) FORGE_DIR="$2" ;;
          --port) PORT="$2" ;; --tunnel) TUNNEL="$2" ;; --cuda) CUDA_INDEX="$2" ;;
          --vram-flag) VRAM_FLAG="$2" ;; --forge-args) EXTRA_FORGE_ARGS="$2" ;;
          --only) ONLY_STAGES="$2" ;; --skip) SKIP_STAGES="$2" ;;
        esac
        shift 2 ;;
      --no-launch) DO_LAUNCH=0; shift ;;
      --restart) RESTART=1; shift ;;
      --smoke-test) SMOKE_TEST=1; shift ;;
      --force) FORCE=1; shift ;;
      --fallback-fp16) WAI_NO_FALLBACK=0; shift ;;
      --no-fallback) WAI_NO_FALLBACK=1; shift ;;
      --status) MODE=status; shift ;; --doctor) MODE=doctor; shift ;;
      --clean) MODE=clean; shift ;;
      --diagnostics) MODE=diagnostics; shift ;;
      --print-models) print_models; exit 0 ;;
      --list-stages) printf '%s\n' "${DEFAULT_STAGES[@]}"; exit 0 ;;
      -h|--help) usage; exit 0 ;; -V|--version) echo "install.sh $INSTALLER_VERSION"; exit 0 ;;
      *) bad "Cờ không hợp lệ: $1"; exit 2 ;;
    esac
  done
}
validate_args() {
  case "$MODEL_ID" in fp16|fp8|int8|hswq) ;; custom)
    if [[ -n "$MODEL_URL_OVERRIDE" && -n "$MODEL_FILE_OVERRIDE" && -n "$MODEL_SHA_OVERRIDE" ]]; then
      :
    elif load_model_cache; then
      : # --status/--doctor/--only launch được dùng metadata đã lưu, không cần token/URL
    else
      bad "--model custom cần --model-url, --model-file và --model-sha (hoặc metadata đã lưu)."; exit 2
    fi ;;
    *) bad "Model '$MODEL_ID' không hợp lệ. Chọn fp16, fp8, int8, hswq hoặc custom."; exit 2 ;;
  esac
  if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || (( 10#$PORT <= 0 || 10#$PORT >= 65536 )); then
    bad "--port phải trong 1–65535."; exit 2
  fi
  case "$TUNNEL" in cloudflared|share|none) ;; *) bad "--tunnel không hợp lệ."; exit 2 ;; esac
  case "$CUDA_INDEX" in auto|cu130|cu128|cu126) ;; *) bad "--cuda không hợp lệ."; exit 2 ;; esac
  local list st key
  for list in "$ONLY_STAGES" "$SKIP_STAGES"; do
    for st in ${list//,/ }; do in_list "${DEFAULT_STAGES[*]}" "$st" || { bad "Stage '$st' không hợp lệ."; exit 2; }; done
  done
  for key in REPO_DIR FORGE_DIR MODEL_DIR STATE_DIR RUNTIME_DIR; do
    [[ -n "${!key}" && "${!key}" != / && "${!key}" != *$'\n'* ]] || { bad "Đường dẫn $key không an toàn/rỗng."; exit 2; }
    printf -v "$key" '%s' "$("$PY_BIN" -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "${!key}")"
  done
  [[ -z "$MODEL_FILE_OVERRIDE" || ( "$MODEL_FILE_OVERRIDE" == *.safetensors && "$MODEL_FILE_OVERRIDE" != */* && "$MODEL_FILE_OVERRIDE" != .* ) ]] \
    || { bad "--model-file phải là tên file .safetensors (không chứa thư mục)."; exit 2; }
  [[ -z "$MODEL_SHA_OVERRIDE" || "$MODEL_SHA_OVERRIDE" =~ ^[a-fA-F0-9]{64}$ ]] \
    || { bad "SHA256 phải có 64 ký tự hex."; exit 2; }
  [[ -z "$MODEL_MIN_OVERRIDE" || "$MODEL_MIN_OVERRIDE" =~ ^[0-9]+$ ]] \
    || { bad "MODEL_MIN_BYTES không hợp lệ."; exit 2; }
  # Không để EXTRA_FORGE_ARGS âm thầm ghi đè đường dẫn/port/file cấu hình do bộ cài quản lý.
  # --ckpt-dirs có action=append nên vẫn cho phép thêm thư mục khác.
  "$PY_BIN" - "$EXTRA_FORGE_ARGS" <<'PYARGS' || { bad "--forge-args không hợp lệ."; exit 2; }
import shlex, sys
try:
    args = shlex.split(sys.argv[1])
except ValueError:
    sys.exit("--forge-args có dấu nháy không hợp lệ.")
reserved = {"--ui-settings-file", "--ui-config-file", "--data-dir", "--model-ref", "--port",
            "--server-name", "--ckpt", "--nowebui", "--disable-all-extensions", "--ui-debug-mode",
            "--api-auth", "--gradio-auth", "--gradio-auth-path", "--ngrok", "--ngrok-authtoken"}
for arg in args:
    flag = arg.split("=", 1)[0]
    if flag in reserved:
        sys.exit(f"Cờ {flag} xung đột đường dẫn/chế độ hoặc chứa credential không được lưu; không truyền nó trong --forge-args.")
PYARGS
  if [[ "$SMOKE_TEST" == 1 && ( "$MODE" != install || "$DO_LAUNCH" != 1 ) ]]; then
    bad "--smoke-test cần chế độ cài/verify có API (không dùng với --doctor/--no-launch)."; exit 2
  fi
  if [[ "$SMOKE_TEST" == 1 ]] && ! selected verify; then
    bad "--smoke-test cần stage verify trong --only."; exit 2
  fi
  [[ "$CUDA_INDEX" == auto ]] || CUDA_PICK="$CUDA_INDEX"
}

# Catalog: bản gốc đã có hash; bản cộng đồng lấy URL/hash chính xác từ API lúc cài.
model_ids() { echo "fp16 fp8 int8 hswq"; }

m_field() { # m_field <id> <field>
  case "$1" in
    fp16) case "$2" in
      label) echo "FP16 pruned — bản gốc của WAI0731 (khuyến nghị)" ;;
      file)  echo "waiIllustriousSDXL_v170.safetensors" ;;
      gb)    echo "6.46" ;;
      min)   echo "6800000000" ;;
      sha)   echo "f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04" ;;
      civ)   echo "827184" ;;
      ver)   echo "2883731" ;;
      # Mirror HuggingFace: tải không cần token, SHA256 đã đối chiếu với Civitai.
      hf)    echo "https://huggingface.co/LyliaEngine/waiIllustriousSDXL_v170/resolve/main/waiIllustriousSDXL_v170.safetensors https://huggingface.co/Coercer/Modified_VeryFast_Models_DMD2/resolve/main/Orig_Models_Pruned/waiIllustriousSDXL_v170.safetensors" ;;
      cfg)   echo "6.0" ;; steps) echo "25" ;; sampler) echo "Euler a" ;; clip) echo "2" ;;
      note)  echo "Đúng tham số trên thẻ model: CFG 5–7, steps 15–30, ≥1024×1024." ;;
      warn)  echo "" ;;
    esac ;;
    fp8) case "$2" in
      label) echo "FP8 e4m3 — nhẹ VRAM, lượng tử hoá bởi bên thứ ba" ;;
      file)  echo "waiIllustriousSDXL_v170_fp8_e4m3.safetensors" ;;
      gb)    echo "4.07" ;;
      min)   echo "4200000000" ;;
      sha)   echo "" ;;   # lấy từ API Civitai lúc chạy
      civ)   echo "2451718" ;;
      ver)   echo "" ;;
      hf)    echo "" ;;
      cfg)   echo "6.5" ;; steps) echo "25" ;; sampler) echo "Euler a" ;; clip) echo "2" ;;
      note)  echo "Thẻ model ghi CFG 6–7, Euler Ancestral, clip skip 2." ;;
      warn)  echo "T4 là Turing (sm75), KHÔNG có nhân tensor FP8 — chưa kiểm chứng sinh ảnh trên T4, có thể chậm/lỗi; nếu hỏng hãy dùng --model fp16." ;;
    esac ;;
    int8) case "$2" in
      label) echo "INT8 convrot — lượng tử hoá 8-bit số nguyên" ;;
      file)  echo "waiIllustriousSDXL_v170_int8_convrot.safetensors" ;;
      gb)    echo "4.39" ;;
      min)   echo "4500000000" ;;
      sha)   echo "" ;;
      civ)   echo "2451718" ;;
      ver)   echo "" ;;
      hf)    echo "" ;;
      cfg)   echo "6.5" ;; steps) echo "25" ;; sampler) echo "Euler a" ;; clip) echo "2" ;;
      note)  echo "Cùng nguồn với bản FP8 (WAI-illustrious-Mix-FP8)." ;;
      warn)  echo "Bản lượng tử hoá cộng đồng; tương thích và tốc độ phụ thuộc backend/GPU (thử nghiệm)." ;;
    esac ;;
    hswq) case "$2" in
      label) echo "HSWQ turbo r32 — sinh nhanh (DMD2 + Stabilizer IL + SPO)" ;;
      file)  echo "waiIllustriousSDXL_v170_hswq_r32_turbo.safetensors" ;;
      gb)    echo "4.43" ;;
      min)   echo "4550000000" ;;
      sha)   echo "" ;;
      civ)   echo "2698106" ;;
      ver)   echo "" ;;
      hf)    echo "" ;;
      cfg)   echo "1.0" ;; steps) echo "10" ;; sampler) echo "Euler a" ;; clip) echo "2" ;;
      note)  echo "Bản merge tăng tốc: CFG 1.0, steps 10 (chất lượng cao hơn: CFG 2–3, steps 15–20)." ;;
      warn)  echo "KHÔNG dùng tham số của bản FP16 — CFG 6 có thể làm hỏng ảnh. Bộ dựng prompt đã tự đổi theo." ;;
    esac ;;
    custom) case "$2" in
      label) echo "Checkpoint SDXL tuỳ chỉnh — người dùng cung cấp nguồn và hash" ;;
      gb|min) echo "0" ;;
      cfg) echo "6.0" ;; steps) echo "25" ;; sampler) echo "Euler a" ;; clip) echo "2" ;;
      *) echo "" ;;
    esac ;;
    *) echo "" ;;
  esac
}

print_models() {
  step "Biến thể model WAI-Illustrious-SDXL v17.0"
  printf '%-6s %-8s %-52s %s\n' "ID" "DUNG LƯỢNG" "FILE" "SHA256 CÔNG BỐ"
  local id
  for id in $(model_ids); do
    printf '%-6s %-8s %-52s %s\n' "$id" "$(m_field "$id" gb) GiB" "$(m_field "$id" file)" \
      "$( [[ -n "$(m_field "$id" sha)" ]] && echo "có (kiểm chứng)" || echo "lấy từ API Civitai lúc chạy" )"
  done
  echo
  for id in $(model_ids); do
    printf '%s\n' "── $id: $(m_field "$id" label)"
    printf '   tham số: CFG %s · steps %s · %s · clip skip %s\n' \
      "$(m_field "$id" cfg)" "$(m_field "$id" steps)" "$(m_field "$id" sampler)" "$(m_field "$id" clip)"
    printf '   %s\n' "$(m_field "$id" note)"
    [[ -n "$(m_field "$id" warn)" ]] && printf '   ⚠ %s\n' "$(m_field "$id" warn)"
  done
  echo
  info "Nguồn: Civitai model 827184 (fp16) · 2451718 (fp8/int8) · 2698106 (hswq)."
  info "Chỉ bản fp16 có mirror HuggingFace tải không cần token."
}

# ------------------------------------------------------------------- trạng thái
mark_ok() {
  [[ "$MODE" == install ]] || return 0
  local tmp="$STATE_DIR/$1.ok.tmp"
  printf '%s\n%s\n' "$(date -Is)" "$(fingerprint "$1")" > "$tmp"
  mv -f "$tmp" "$STATE_DIR/$1.ok"
}
mark_time() { [[ ! -f "$STATE_DIR/$1.ok" ]] || head -1 "$STATE_DIR/$1.ok"; }
fingerprint() {
  local script_sha repo_sha
  script_sha=$(sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)
  repo_sha=$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo no-git)
  {
    printf '%s\0' "$INSTALLER_VERSION" "$script_sha" "$1"
    case "$1" in
      repo) printf '%s\0' "$REPO_URL" "$REPO_BRANCH" "$REPO_DIR" ;;
      forge) printf '%s\0' "$FORGE_DIR" "$FORGE_REPO" "$FORGE_BRANCH" ;;
      torch) printf '%s\0' "$FORGE_DIR" "$CUDA_INDEX" "$DRIVER" ;;
      extras) printf '%s\0' "$FORGE_DIR" "$REPO_DIR" "$repo_sha" ;;
      model|launch|verify) printf '%s\0' "$FORGE_DIR" "$MODEL_ID" "$MODEL_DIR" "$MODEL_FILE" "$MODEL_SHA256" "$PORT" "$TUNNEL" "$VRAM_FLAG" "$EXTRA_FORGE_ARGS" ;;
    esac
  } | sha256sum | cut -d' ' -f1
}
repo_ready() {
  local f
  for f in danbooru_e621.csv danbooru_e621_nounderscore.csv danbooru_e621_vi.csv \
    danbooru_e621_vi_translation.csv colab/setup_forge.sh colab/prompt_lib/index.py \
    colab/checkpoint_tools.py colab/diagnostics.py; do
    [[ -s "$REPO_DIR/$f" ]] || return 1
  done
}
extras_ready() {
  local ext="$FORGE_DIR/extensions" f
  for f in a1111-sd-webui-tagcomplete/tags/danbooru_e621.csv \
           a1111-sd-webui-tagcomplete/tags/wai-illustrious-system-tags.csv \
           a1111-sd-webui-tagcomplete/tags/danbooru_e621_vi_translation_wai.csv \
           vi-prompt-builder/scripts/vi_prompt_tab.py; do
    [[ -s "$ext/$f" ]] || return 1
  done
  [[ -s "$FORGE_DIR/config.json" && -s "$FORGE_DIR/styles.csv" ]]
}
torch_ready() {
  [[ -x "$FORGE_DIR/venv/bin/python" ]] || return 1
  "$FORGE_DIR/venv/bin/python" -c 'import torch,torchvision; assert torch.cuda.is_available(); assert torch.ones(4,device="cuda").sum().item()==4; torch.cuda.synchronize()' >/dev/null 2>&1
}
stage_can_resume() {
  [[ "$FORCE" == 0 && -z "$ONLY_STAGES" && -f "$STATE_DIR/$1.ok" ]] || return 1
  [[ "$(sed -n '2p' "$STATE_DIR/$1.ok")" == "$(fingerprint "$1")" ]] || return 1
  case "$1" in
    repo) repo_ready ;;
    forge) [[ -s "$FORGE_DIR/launch.py" && -x "$FORGE_DIR/venv/bin/python" ]] ;;
    torch) torch_ready ;;
    extras) extras_ready ;;
    *) return 1 ;; # môi trường, model, API và verify cần kiểm tra lại, không tin marker cũ
  esac
}
run_stage() {
  local st="$1"
  if ! selected "$st"; then return 0; fi
  if stage_can_resume "$st"; then
    info "[$st] đã xong lúc $(mark_time "$st"), file vẫn còn — bỏ qua."
    return 0
  fi
  CURRENT_STAGE="$st"
  rm -f -- "$STATE_DIR/$st.ok"
  step "Bước $st"
  "stage_$st" # cố ý không đặt trong if/||: errexit phải bắt lỗi bên trong hàm
  mark_ok "$st" # chỉ chạy khi stage trước thành công
  CURRENT_STAGE=""
}

# ------------------------------------------------------------------- preflight
probe_host() {
  local name="$1" url="$2" code
  code=$(curl -s -o /dev/null --connect-timeout 5 --max-time 8 -w '%{http_code}' -I "$url" 2>/dev/null || true)
  if [[ "$code" =~ ^[23][0-9][0-9]$ || "$code" == 401 || "$code" == 403 ]]; then
    ok "  $name: có phản hồi (HTTP $code)"; return 0
  fi
  warn "  $name: chưa kết nối được (HTTP ${code:-000})"; return 1
}
stage_preflight() {
  step "Kiểm tra GPU, ổ đĩa và mạng"
  local t line drv_major free_kb need_gb free_gb
  for t in git curl "$PY_BIN"; do have "$t" || problem "Thiếu lệnh $t."; done
  if have nvidia-smi; then
    line=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null | head -1 || true)
    if [[ -n "$line" ]]; then
      GPU_NAME=$(cut -d, -f1 <<< "$line" | xargs)
      GPU_VRAM_MB=$(cut -d, -f2 <<< "$line" | xargs)
      DRIVER=$(cut -d, -f3 <<< "$line" | xargs)
      ok "GPU: $GPU_NAME · ${GPU_VRAM_MB} MiB · driver $DRIVER"
    fi
  fi
  if [[ -z "$GPU_NAME" ]]; then
    problem "Không có GPU. Colab → Runtime → Change runtime type → GPU T4."
  fi
  [[ "$GPU_VRAM_MB" =~ ^[0-9]+$ ]] || GPU_VRAM_MB=0
  if (( GPU_VRAM_MB > 0 && GPU_VRAM_MB < 8000 )); then
    warn "VRAM <8 GB; model có thể thiếu bộ nhớ."
    [[ -n "$VRAM_FLAG" ]] || VRAM_FLAG="--lowvram"
  fi
  drv_major="${DRIVER%%.*}"
  if [[ "$CUDA_INDEX" == auto && "$drv_major" =~ ^[0-9]+$ ]]; then
    if (( 10#$drv_major >= 580 )); then CUDA_PICK=cu130
    elif (( 10#$drv_major >= 570 )); then CUDA_PICK=cu128
    else CUDA_PICK=cu126; fi
  fi
  info "PyTorch bắt đầu với $CUDA_PICK; có kiểm tra kernel CUDA thật trước khi dùng."

  need_gb=$(awk -v g="$(m_field "$MODEL_ID" gb)" 'BEGIN{printf "%.1f",g+14}')
  # Chạy lại không cần cấp lại dung lượng cho model/venv đã có.
  if [[ -x "$FORGE_DIR/venv/bin/python" && -f "$MODEL_DIR/$(m_field "$MODEL_ID" file)" ]]; then need_gb=2; fi
  free_kb=$(df -Pk "$RUNTIME_DIR" 2>/dev/null | awk 'NR==2{print $4}' || true)
  [[ -n "$free_kb" ]] || free_kb=$(df -Pk / | awk 'NR==2{print $4}')
  free_gb=$(awk -v k="${free_kb:-0}" 'BEGIN{printf "%.1f",k/1048576}')
  if awk -v f="$free_gb" -v n="$need_gb" 'BEGIN{exit !(f<n)}'; then
    problem "Còn ${free_gb} GiB, cần khoảng ${need_gb} GiB. Dọn file không dùng hoặc khởi tạo lại runtime."
  else
    ok "Ổ đĩa còn ${free_gb} GiB (cần ~${need_gb} GiB)."
  fi
  probe_host github.com https://github.com/ || problem "Không kết nối được GitHub."
  probe_host pypi.org https://pypi.org/simple/ || problem "Không kết nối được PyPI."
  probe_host download.pytorch.org https://download.pytorch.org/whl/ || problem "Không kết nối được nguồn PyTorch CUDA."
  probe_host huggingface.co https://huggingface.co/ || true
  # API 401/403 = host có phản hồi, KHÔNG có nghĩa là token/quyền tải hợp lệ.
  probe_host civitai.com "$CIVITAI_API_BASE/models/$(m_field "$MODEL_ID" civ)" || true
  if [[ "$MODE" == install ]] && ! have aria2c && have apt-get; then
    info "Thử cài aria2 để tải nhiều luồng (không bắt buộc) ..."
    (apt-get update -qq && apt-get install -y -qq aria2) >/dev/null 2>&1 \
      || warn "Không cài được aria2; dùng wget/curl."
  fi
  return 0
}

# ------------------------------------------------------------------- repo + stage delegate
locate_setup() {
  local self_dir
  self_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  # Repo là nguồn chuẩn sau khi cập nhật; không ưu tiên buddy /content/setup_forge.sh
  # cũ còn sót từ một lần sửa lỗi/notebook khác.
  if [[ -f "$REPO_DIR/colab/setup_forge.sh" ]]; then SETUP="$REPO_DIR/colab/setup_forge.sh"
  else SETUP="$self_dir/setup_forge.sh"; fi
}
repo_git() {
  if [[ -n "$GITHUB_TOKEN" ]]; then
    local auth
    auth=$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.https://github.com/.extraheader \
      GIT_CONFIG_VALUE_0="Authorization: Basic $auth" git -C "$REPO_DIR" "$@"
  else git -C "$REPO_DIR" "$@"; fi
}
stage_repo() {
  if [[ -s "$REPO_DIR/danbooru_e621.csv" && -s "$REPO_DIR/colab/setup_forge.sh" ]]; then
    if [[ -d "$REPO_DIR/.git" ]]; then
      local branch origin
      branch=$(git -C "$REPO_DIR" branch --show-current)
      origin=$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)
      if [[ "$branch" != "$REPO_BRANCH" ]]; then
        warn "Repo đang ở nhánh $branch, không tự chuyển nhánh. Dùng REPO_DIR mới hoặc chọn --branch $branch."
      elif [[ "${origin%.git}" != "${REPO_URL%.git}" ]]; then
        warn "Origin không khớp REPO_URL; không tự fetch/cập nhật repo khác."
      elif [[ -n "$(git -C "$REPO_DIR" status --porcelain --untracked-files=normal)" ]]; then
        warn "Repo có sửa đổi local — giữ nguyên, không reset/ghi đè."
      elif repo_git fetch --quiet origin "$REPO_BRANCH" && repo_git merge --quiet --ff-only FETCH_HEAD; then
        ok "Repo được cập nhật fast-forward, không chuyển nhánh/không reset."
      else
        warn "Không cập nhật được (mạng hoặc lịch sử phân kỳ); giữ checkout hiện có."
      fi
    fi
    repo_ready || die "Repo cũ/thiếu checkpoint_tools.py hoặc diagnostics.py. Cập nhật cùng nhánh, giữ thay đổi local; không reset hard."
    ok "Dùng kho prompt sẵn có: $REPO_DIR (không xoá thay đổi của bạn)."
    return 0
  fi
  if [[ -e "$REPO_DIR" && -n "$(ls -A "$REPO_DIR" 2>/dev/null)" ]]; then
    die "Thư mục $REPO_DIR đã có dữ liệu nhưng thiếu file cần thiết. Không xoá; kiểm tra nhánh hoặc dùng REPO_DIR khác."
  fi
  mkdir -p "$(dirname "$REPO_DIR")"
  local tmp auth rc=0
  tmp=$(mktemp -d "$(dirname "$REPO_DIR")/.wai-repo.XXXXXX")
  info "Clone đúng nhánh $REPO_BRANCH ..."
  if [[ -n "$GITHUB_TOKEN" ]]; then
    auth=$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)
    # Header chỉ nằm trong environment của lệnh git; URL origin không chứa token.
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.https://github.com/.extraheader \
      GIT_CONFIG_VALUE_0="Authorization: Basic $auth" \
      git clone --quiet --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$tmp" 2>/dev/null || rc=$?
  else
    git clone --quiet --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$tmp" 2>/dev/null || rc=$?
  fi
  if (( rc )); then
    rm -rf -- "$tmp" # chỉ thư mục tạm do chính mktemp vừa tạo
    die "Không clone được nhánh $REPO_BRANCH. Kiểm tra URL/nhánh và quyền đọc repo."
  fi
  if [[ -d "$REPO_DIR" ]]; then rmdir -- "$REPO_DIR"; fi # chỉ chấp nhận thư mục rỗng
  mv "$tmp" "$REPO_DIR"
  repo_ready || die "Repo thiếu kho prompt hoặc colab/setup_forge.sh. Kiểm tra nhánh."
  ok "Kho prompt đã có: $REPO_DIR"
}
run_setup() {
  locate_setup # phải được thiết lập lại khi chạy --only hoặc resume (không lệ thuộc stage repo)
  [[ -s "$SETUP" ]] || die "Chưa có $SETUP. Chạy lại toàn bộ bộ cài hoặc stage repo trước."
  grep -q '^SETUP_API_VERSION=2$' "$SETUP" \
    || die "setup_forge.sh đang là bản cũ/không tương thích. Cập nhật repo cùng nhánh rồi chạy lại; không dùng lẫn hai bản bộ cài."
  env REPO_URL="$REPO_URL" REPO_BRANCH="$REPO_BRANCH" REPO_DIR="$REPO_DIR" GITHUB_TOKEN="$GITHUB_TOKEN" \
  FORGE_DIR="$FORGE_DIR" FORGE_REPO="$FORGE_REPO" FORGE_BRANCH="$FORGE_BRANCH" \
  MODEL_DIR="$MODEL_DIR" MODEL_FILE="$MODEL_FILE" MODEL_SHA256="$MODEL_SHA256" \
  MODEL_MIN_BYTES="$MODEL_MIN_BYTES" MODEL_LABEL="$MODEL_LABEL" MODEL_URL="$MODEL_URLS_STR" \
  CIVITAI_TOKEN="$CIVITAI_TOKEN" CIVITAI_VERSION_ID="$CIVITAI_VERSION_ID" \
  PORT="$PORT" TUNNEL="$TUNNEL" VRAM_FLAG="$VRAM_FLAG" PY="$PY_BIN" \
  TORCH_INDEX="$CUDA_PICK" FORCE_TORCH="$FORCE" EXTRA_FORGE_ARGS="$EXTRA_FORGE_ARGS" \
  WAI_RUNTIME_DIR="$RUNTIME_DIR" VI_PROMPT_ROOT="$REPO_DIR" \
  WAI_PROFILE_MODEL_ID="$MODEL_ID" WAI_PROFILE_CFG="$(m_field "$MODEL_ID" cfg)" \
  WAI_PROFILE_STEPS="$(m_field "$MODEL_ID" steps)" WAI_PROFILE_SAMPLER="$(m_field "$MODEL_ID" sampler)" \
  WAI_PROFILE_HIRES_STEPS="$( [[ "$MODEL_ID" == hswq ]] && echo 10 || echo 20 )" \
    bash "$SETUP" "$1" 9>&- # child/Forge không giữ khoá của bộ cài
}
stage_forge() { run_setup forge; }
stage_torch() { run_setup torch; }
stage_extras() { run_setup extras; }

# ------------------------------------------------------------------- model metadata
civitai_resolve() { # chỉ khớp đúng tên file v17; không tự chọn v16/v18 hay variant khác
  CIVITAI_TOKEN="$CIVITAI_TOKEN" CIVITAI_API_BASE="$CIVITAI_API_BASE" "$PY_BIN" - "$1" "$2" <<'PYEOF'
import json, os, re, sys, urllib.request, urllib.error
model_id, want = sys.argv[1], sys.argv[2]
base = os.environ.get("CIVITAI_API_BASE", "https://civitai.com/api/v1").rstrip("/")
tok = os.environ.get("CIVITAI_TOKEN", "").strip()
req = urllib.request.Request(f"{base}/models/{model_id}", headers={
    "User-Agent": "wai-colab-installer/1.0", "Accept": "application/json",
    **({"Authorization": f"Bearer {tok}"} if tok else {}),
})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
except urllib.error.HTTPError as e:
    sys.stderr.write(f"Civitai HTTP {e.code}. Kiểm tra CIVITAI_TOKEN/quyền tải nếu là 401/403.\n")
    sys.exit(3)
except Exception as e:
    sys.stderr.write(f"Civitai API chưa kết nối được ({type(e).__name__}).\n")
    sys.exit(4)
versions = data.get("modelVersions") or []
if not versions:
    sys.stderr.write("Không có modelVersions; có thể nội dung NSFW cần token/quyền truy cập.\n")
    sys.exit(5)
for v in versions:
    for f in v.get("files") or []:
        if f.get("name") != want: continue
        sha = ((f.get("hashes") or {}).get("SHA256") or "").lower()
        dl = f.get("downloadUrl") or v.get("downloadUrl") or ""
        size = int(float(f.get("sizeKB") or 0) * 1024)
        if not re.fullmatch(r"[a-f0-9]{64}", sha) or not dl or size <= 0:
            sys.stderr.write("File thiếu URL, dung lượng hoặc SHA256 hợp lệ. Không tải bản chưa xác minh.\n")
            sys.exit(7)
        if "fileId=" not in dl and not f.get("primary") and f.get("id"):
            dl += ("&" if "?" in dl else "?") + f"fileId={f['id']}"
        # Unit Separator không phải IFS whitespace: bảo toàn trường rỗng, tên version có dấu cách.
        fields = [dl, sha, str(size), f["name"], v.get("name") or "", str(v.get("id") or "")]
        if any("\n" in x or "\x1f" in x for x in fields): sys.exit(7)
        print("\x1f".join(fields))
        sys.exit(0)
sys.stderr.write(f"Không còn file đúng tên '{want}'. Không tự chọn phiên bản khác.\n")
sys.exit(6)
PYEOF
}
# Helper dùng cho mirror tùy chỉnh: /raw/ mới là pointer LFS, /resolve/ là file nhị phân.
hf_lfs_sha256() {
  "$PY_BIN" - "$1" <<'PYEOF'
import re, sys, urllib.request
url = sys.argv[1].replace("/resolve/", "/raw/")
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        text = r.read(600).decode("utf-8", "ignore")
except Exception:
    sys.exit(1)
m = re.search(r"oid sha256:([0-9a-f]{64})", text)
print(m.group(1) if m else "")
PYEOF
}
init_model_spec() {
  MODEL_FILE="${MODEL_FILE_OVERRIDE:-$(m_field "$MODEL_ID" file)}"
  MODEL_SHA256="${MODEL_SHA_OVERRIDE:-$(m_field "$MODEL_ID" sha)}"
  MODEL_LABEL="$(m_field "$MODEL_ID" label)"
  MODEL_MIN_BYTES="${MODEL_MIN_OVERRIDE:-$(m_field "$MODEL_ID" min)}"
  CIVITAI_VERSION_ID="$(m_field "$MODEL_ID" ver)"
  MODEL_URLS_STR="${MODEL_URL_OVERRIDE:-$(m_field "$MODEL_ID" hf)}"
}
load_model_cache() {
  [[ -f "$STATE_DIR/model.json" ]] || return 1
  local out
  out=$("$PY_BIN" - "$STATE_DIR/model.json" "$MODEL_ID" "$MODEL_DIR" "$MODEL_FILE_OVERRIDE" "$MODEL_SHA_OVERRIDE" <<'PYCACHE'
import json, os, re, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    file, sha = d["file"], d["sha256"]
    if d["id"] != sys.argv[2] or d["dir"] != sys.argv[3]: sys.exit(1)
    if sys.argv[4] and file != sys.argv[4]: sys.exit(1)
    if sys.argv[5] and sha.lower() != sys.argv[5].lower(): sys.exit(1)
    if os.path.basename(file) != file or not file.endswith(".safetensors"): sys.exit(1)
    if not re.fullmatch(r"[a-fA-F0-9]{64}", sha): sys.exit(1)
    fields = [file, sha.lower(), str(int(d["min_bytes"])), str(d.get("version_id") or "")]
    if any("\n" in x or "\x1f" in x for x in fields): sys.exit(1)
    print("\x1f".join(fields))
except (OSError, ValueError, KeyError, TypeError):
    sys.exit(1)
PYCACHE
  ) || return 1
  IFS=$'\x1f' read -r MODEL_FILE MODEL_SHA256 MODEL_MIN_BYTES CIVITAI_VERSION_ID <<< "$out"
  [[ -z "$MODEL_MIN_OVERRIDE" ]] || MODEL_MIN_BYTES="$MODEL_MIN_OVERRIDE"
  return 0
}
resolve_model() {
  [[ "$SPEC_READY" == 0 ]] || return 0
  init_model_spec
  # Metadata lưu không có token/URL riêng. Resume có file sẵn không phải hỏi API lại.
  if [[ -z "$MODEL_URL_OVERRIDE" && "$FORCE" == 0 ]] && load_model_cache; then
    if [[ -f "$MODEL_DIR/$MODEL_FILE" || "$MODE" != install ]] || ! selected model; then
      SPEC_READY=1; return 0
    fi
  fi
  # --doctor/--only launch không cần tải/resolve mạng; kiểm tra tên file/cache đã có.
  if [[ "$MODE" != install ]] || ! selected model; then SPEC_READY=1; return 0; fi
  if [[ -z "$MODEL_URL_OVERRIDE" && "$MODEL_ID" != fp16 && "$MODEL_ID" != custom ]]; then
    step "Lấy URL + SHA256 của $MODEL_ID từ Civitai"
    local out url sha size name vername verid
    if out=$(civitai_resolve "$(m_field "$MODEL_ID" civ)" "$MODEL_FILE"); then
      IFS=$'\x1f' read -r url sha size name vername verid <<< "$out"
      MODEL_URLS_STR="$url"; MODEL_FILE="$name"
      MODEL_SHA256="${MODEL_SHA_OVERRIDE:-$sha}"
      MODEL_MIN_BYTES="${MODEL_MIN_OVERRIDE:-$(( size - size / 32 ))}"
      CIVITAI_VERSION_ID="$verid"
      ok "Đúng file v17: $MODEL_FILE (phiên bản $vername)."
    elif [[ "$WAI_NO_FALLBACK" == 0 ]]; then
      warn "Bạn đã cho phép --fallback-fp16: chuyển sang bản gốc FP16."
      MODEL_ID=fp16; init_model_spec
    else
      die "Chưa có nguồn xác minh cho $MODEL_ID. Cấp CIVITAI_TOKEN qua Colab Secrets, hoặc chọn --model fp16. Không tự đổi model."
    fi
  fi
  [[ "$MODEL_SHA256" =~ ^[a-fA-F0-9]{64}$ ]] || die "Chưa có SHA256 hợp lệ cho model. Cấp --model-sha."
  MODEL_SHA256="${MODEL_SHA256,,}"
  [[ "$MODEL_MIN_BYTES" =~ ^[0-9]+$ ]] || die "Metadata dung lượng không hợp lệ."
  SPEC_READY=1
}
save_settings() {
  [[ "$MODE" == install ]] || return 0
  local key
  for key in "${CONFIG_KEYS[@]}"; do export "${key?}"; done
  export MODEL_FILE MODEL_SHA256 MODEL_MIN_BYTES CIVITAI_VERSION_ID
  "$PY_BIN" - "$STATE_DIR" "${CONFIG_KEYS[@]}" <<'PYSAVE'
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
def write(name, data):
    tmp = root / (name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(root / name)
write("settings.json", {k: os.environ[k] for k in sys.argv[2:]})
if os.environ.get("MODEL_SHA256"):
    write("model.json", {"id": os.environ["MODEL_ID"], "dir": os.environ["MODEL_DIR"],
                        "file": os.environ["MODEL_FILE"], "sha256": os.environ["MODEL_SHA256"],
                        "min_bytes": int(os.environ["MODEL_MIN_BYTES"]),
                        "version_id": os.environ.get("CIVITAI_VERSION_ID", "")})
PYSAVE
}
save_profile() {
  # App Gradio độc lập cũng đọc file này, không cần kế thừa environment của Bash.
  [[ -d "$REPO_DIR/colab" ]] || return 0
  "$PY_BIN" - "$REPO_DIR/colab/assets" "$MODEL_ID" <<'PYPROFILE'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=True)
tmp = root / "model_profile.json.tmp"
tmp.write_text(json.dumps({"WAI_PROFILE_MODEL_ID": sys.argv[2]}), encoding="utf-8")
tmp.replace(root / "model_profile.json")
PYPROFILE
}
stage_model() {
  resolve_model
  step "Model $MODEL_ID → $MODEL_DIR/$MODEL_FILE"
  local note
  note=$(m_field "$MODEL_ID" warn)
  [[ -z "$note" ]] || warn "$note"
  run_setup model
  save_settings
  save_profile
}

# ------------------------------------------------------------------- API / launch
api_ready() { curl -fsS --max-time 3 "http://127.0.0.1:$PORT/sdapi/v1/sd-models" >/dev/null 2>&1; }
owned_forge() {
  [[ -s "$RUNTIME_DIR/forge.pid" ]] || return 1
  local pid
  pid=$(cat "$RUNTIME_DIR/forge.pid")
  [[ "$pid" =~ ^[0-9]+$ ]] && [[ -r "/proc/$pid/cmdline" ]] || return 1
  tr '\0' ' ' < "/proc/$pid/cmdline" | grep -Fq -- "$FORGE_DIR/launch.py"
}
stage_launch() {
  resolve_model
  [[ -f "$MODEL_DIR/$MODEL_FILE" ]] || die "Chưa có model đã chọn. Chạy stage model trước."
  local same=0
  [[ ! -f "$STATE_DIR/running.sha" ]] || [[ "$(cat "$STATE_DIR/running.sha")" != "$(fingerprint launch)" ]] || same=1
  if api_ready && [[ "$same" == 1 && "$RESTART" == 0 && "$FORCE" == 0 ]]; then
    ok "Forge đang chạy đúng cấu hình — không khởi động trùng."
    return 0
  fi
  if api_ready && ! owned_forge; then
    die "Cổng $PORT đã có dịch vụ không do bộ cài quản lý. Không tự dừng nó; đổi --port hoặc dừng dịch vụ đó."
  fi
  if owned_forge && [[ "$same" == 0 || "$RESTART" == 1 || "$FORCE" == 1 ]]; then
    run_setup stop
  fi
  save_settings
  save_profile
  # Lưu trước khi launch để lần gọi lại chờ/reuse process đang khởi động, không chạy trùng.
  fingerprint launch > "$STATE_DIR/running.sha"
  run_setup launch-bg
  api_ready || die "Stage launch trả về nhưng API chưa phản hồi. Xem $RUNTIME_DIR/forge.log."
}

# ------------------------------------------------------------------- verify (đọc-only)
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "  $label"
  else bad "  $label"; VERIFY_FAIL=$((VERIFY_FAIL + 1)); fi
  return 0
}
check_detail() {
  local label="$1" detail; shift
  if detail=$("$@" 2>&1); then ok "  $label"
  else
    bad "  $label"; VERIFY_FAIL=$((VERIFY_FAIL + 1))
    # Helper checkpoint chỉ trả thông tin công khai/error ngắn, không dump options/log.
    [[ -z "$detail" ]] || printf '%s\n' "${detail: -2500}" >&2
  fi
  return 0
}
valid_model_file() {
  [[ -s "$MODEL_DIR/$MODEL_FILE" && "$MODEL_SHA256" =~ ^[a-fA-F0-9]{64}$ ]] || return 1
  "$PY_BIN" "$REPO_DIR/colab/checkpoint_tools.py" validate "$MODEL_DIR/$MODEL_FILE" --sha "$MODEL_SHA256" --quiet
}
valid_tac_config() {
  "$PY_BIN" - "$FORGE_DIR/config.json" <<'PYCFG'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    assert d["tac_tagFile"] == "danbooru_e621.csv"
    assert d["tac_translation.translationFile"] == "danbooru_e621_vi_translation_wai.csv"
    assert d["tac_translation.searchByTranslation"] is True
    assert d["tac_translation.oldFormat"] is False
except (OSError, ValueError, KeyError, AssertionError, TypeError): sys.exit(1)
PYCFG
}
model_in_api() {
  "$PY_BIN" "$REPO_DIR/colab/checkpoint_tools.py" api "http://127.0.0.1:$PORT" \
    "$MODEL_DIR/$MODEL_FILE" --sha "$MODEL_SHA256" --registry-only
}
model_selected_api() {
  "$PY_BIN" "$REPO_DIR/colab/checkpoint_tools.py" api "http://127.0.0.1:$PORT" \
    "$MODEL_DIR/$MODEL_FILE" --sha "$MODEL_SHA256"
}

stage_verify() {
  resolve_model
  VERIFY_FAIL=0
  check "Forge Neo + venv" test -x "$FORGE_DIR/venv/bin/python"
  check "Kho prompt đủ 4 CSV" repo_ready
  check_detail "Model $MODEL_FILE hợp lệ và khớp SHA256" valid_model_file
  check "Tagcomplete + extension Prompt VN + bản dịch" extras_ready
  check "Cấu hình tìm bằng tiếng Việt của Forge" valid_tac_config
  check "PyTorch chạy được kernel CUDA" torch_ready
  if [[ -x "$FORGE_DIR/venv/bin/python" ]]; then
    check "prompt_lib import được" env PYTHONPATH="$REPO_DIR/colab" "$FORGE_DIR/venv/bin/python" -c 'import prompt_lib; assert prompt_lib.SYSTEM_TAGS'
  fi
  if [[ ! -s "$FORGE_DIR/models/ESRGAN/RealESRGAN_x4plus_anime_6B.pth" ]]; then
    warn "Chưa có upscaler anime (không chặn cài); tải lại với --only extras."
  fi
  if [[ "$DO_LAUNCH" == 1 ]]; then
    check "API Forge phản hồi ở cổng $PORT" api_ready
    if api_ready; then
      check_detail "Forge quét đúng đường dẫn checkpoint (không chỉ tên file)" model_in_api
      check_detail "Preset XL và checkpoint đang chọn nhất quán" model_selected_api
      if [[ "$SMOKE_TEST" == 1 && "$VERIFY_FAIL" == 0 ]]; then
        info "Sinh 1 ảnh thử để buộc nạp trọng số thật; không phải benchmark/chứng nhận chất lượng."
        check_detail "GPU sinh ảnh thử bằng đúng hash checkpoint" "$PY_BIN" "$REPO_DIR/colab/checkpoint_tools.py" \
          smoke "http://127.0.0.1:$PORT" "$MODEL_DIR/$MODEL_FILE" --sha "$MODEL_SHA256" --output "$RUNTIME_DIR/checkpoint-smoke.png"
      fi
    fi
  fi
  if (( VERIFY_FAIL )); then
    bad "$VERIFY_FAIL kiểm tra chưa đạt."
    printf 'Sửa theo hạng mục; ví dụ --only model,extras hoặc --only launch --restart.\nXem log: tail -50 %s/forge.log\n' "$RUNTIME_DIR"
    return 1
  fi
  if [[ "$SMOKE_TEST" == 1 && "$DO_LAUNCH" == 1 ]]; then
    ok "Ảnh thử: $RUNTIME_DIR/checkpoint-smoke.png"
  elif [[ "$DO_LAUNCH" == 1 ]]; then
    info "Đã xác minh đăng ký/chọn checkpoint; chưa sinh ảnh GPU. Thêm --smoke-test nếu muốn thử nạp thật."
  fi
  ok "Mọi kiểm tra đều đạt."
}
public_link() {
  local file pattern
  if [[ "$TUNNEL" == cloudflared ]]; then file="$RUNTIME_DIR/cloudflared.log"; pattern='https://[a-z0-9-]+\.trycloudflare\.com'
  else file="$RUNTIME_DIR/forge.log"; pattern='https://[a-z0-9.-]+\.gradio\.live'; fi
  [[ ! -f "$file" ]] || grep -oE "$pattern" "$file" | head -1 || true
}
stage_status() {
  step "Trạng thái cài đặt"
  printf '%-10s %-12s %s\n' STAGE 'TRẠNG THÁI' 'THỜI ĐIỂM'
  local st
  for st in "${DEFAULT_STAGES[@]}"; do
    if [[ -f "$STATE_DIR/$st.ok" ]]; then printf '%-10s %-12s %s\n' "$st" 'đã xong' "$(mark_time "$st")"
    else printf '%-10s %-12s —\n' "$st" 'chưa'; fi
  done
  info "Marker là lịch sử; --doctor mới kiểm tra file/API hiện tại."
  info "Biến thể: $MODEL_ID · model dir: $MODEL_DIR · Forge: $FORGE_DIR"
  if [[ -d "$MODEL_DIR" ]]; then find "$MODEL_DIR" -maxdepth 1 -name '*.safetensors*' -printf '  %f (%s byte)\n'; fi
  if api_ready; then
    ok "API đang chạy ở cổng $PORT"; info "Link public: $(public_link)"
  else info "Forge chưa phản hồi ở cổng $PORT"; fi
  return 0
}
stage_doctor() {
  step "KHÁM BỆNH — không cài/sửa gì"
  stage_preflight
  stage_status
  if stage_verify; then :; fi
  if (( HALT_COUNT || VERIFY_FAIL )); then
    bad "$HALT_COUNT vấn đề môi trường và $VERIFY_FAIL kiểm tra cài đặt chưa đạt."
    return 1
  fi
  ok "Môi trường sẵn sàng."
}
stage_clean() {
  if [[ -d "$STATE_DIR" ]]; then
    local st
    for st in "${DEFAULT_STAGES[@]}"; do rm -f -- "$STATE_DIR/$st.ok"; done
  fi
  ok "Đã xoá marker .ok; giữ cấu hình, model, ảnh và repo."
}
summary() {
  ok "Các bước được chọn đã hoàn tất."
  info "Model $MODEL_ID: CFG $(m_field "$MODEL_ID" cfg) · steps $(m_field "$MODEL_ID" steps) · $(m_field "$MODEL_ID" sampler)."
  if selected launch && api_ready; then
    local link
    link=$(public_link)
    [[ -z "$link" ]] || ok "Mở Forge: $link"
    info "Dùng tab Prompt VN hoặc gõ tiếng Việt trong ô prompt."
  elif [[ "$DO_LAUNCH" == 0 ]]; then info "Chưa khởi động Forge (--no-launch)."; fi
  info "Ảnh: $FORGE_DIR/outputs/txt2img-images/ · Log: $LOG"
  info "Mọi dữ liệu ở /content sẽ mất khi runtime kết thúc; tải ảnh về trước khi ngắt phiên."
}

# ------------------------------------------------------------------- main
main() {
  load_saved_settings
  parse_args "$@"
  validate_args
  init_model_spec
  locate_setup
  if [[ "$MODE" == status ]]; then stage_status; return 0; fi
  if [[ "$MODE" == clean ]]; then stage_clean; return 0; fi
  if [[ "$MODE" == diagnostics ]]; then
    "$PY_BIN" "$REPO_DIR/colab/diagnostics.py" --repo-dir "$REPO_DIR" --forge-dir "$FORGE_DIR" \
      --model-dir "$MODEL_DIR" --model-file "$MODEL_FILE" --state-dir "$STATE_DIR" --port "$PORT"
    return 0
  fi
  if [[ "$MODE" == doctor ]]; then
    # Không ghi marker/config và không tải metadata hay dependencies trong doctor.
    if stage_doctor; then return 0; else return 1; fi
  fi
  umask 077
  mkdir -p "$STATE_DIR" "$RUNTIME_DIR" "$(dirname "$LOG")"
  if have flock; then
    exec 9> "$STATE_DIR/install.lock"
    flock -n 9 || die "Một bộ cài khác đang chạy. Chờ nó hoàn tất rồi chạy lại."
  fi
  # Log cùng màn hình; redactor không cho token/query credential lọt vào log.
  exec > >(
    GITHUB_TOKEN="$GITHUB_TOKEN" CIVITAI_TOKEN="$CIVITAI_TOKEN" "$PY_BIN" -u -c '
import os,re,sys
secrets=[os.environ.get(k, "") for k in ("GITHUB_TOKEN","CIVITAI_TOKEN")]
for line in sys.stdin:
    for token in secrets:
        if token: line=line.replace(token,"<redacted>")
    line=re.sub(r"(?i)([?&](?:token|api_key|access_token)=)[^\s&]+",r"\1<redacted>",line)
    sys.stdout.write(line); sys.stdout.flush()
' | tee -a "$LOG"
  ) 2>&1
  step "BỘ CÀI WAI v17 + Forge Neo + prompt tiếng Việt ($INSTALLER_VERSION)"
  info "Model=$MODEL_ID · tunnel=$TUNNEL · port=$PORT"
  local t0=$SECONDS st
  for st in "${DEFAULT_STAGES[@]}"; do run_stage "$st"; done
  save_settings
  summary
  info "Thời gian: $(( (SECONDS-t0)/60 )) phút $(( (SECONDS-t0)%60 )) giây."
}

# Cho phép source trong test để kiểm tra hàm bằng fixture, không chạy cài thật.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
