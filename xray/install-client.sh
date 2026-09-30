#!/usr/bin/env bash
# Install the same fixed Xray release as the server, without changing V2Ray.
set -euo pipefail
umask 077

XRAY_VERSION='26.3.27'
case "$(uname -m)" in
  x86_64|amd64)
    archive='Xray-linux-64.zip'
    expected_sha256='23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae'
    ;;
  aarch64|arm64)
    archive='Xray-linux-arm64-v8a.zip'
    expected_sha256='4d30283ae614e3057f730f67cd088a42be6fdf91f8639d82cb69e48cde80413c'
    ;;
  *) printf '不支持的架构：%s\n' "$(uname -m)" >&2; exit 1 ;;
esac
if [[ "$(uname -s)" != Linux ]]; then
  printf '此安装脚本仅适用于 Linux。\n' >&2
  exit 1
fi
if (( $# > 1 )); then
  printf '用法：bash install-client.sh [安装目录]\n' >&2
  exit 1
fi
client_dir="${1:-$HOME/.local/share/xray-client}"
for program in curl sha256sum python3 install; do
  command -v "$program" >/dev/null || { printf '缺少命令：%s\n' "$program" >&2; exit 1; }
done
if [[ -e "$client_dir/xray" || -L "$client_dir/xray" ]]; then
  printf '已存在 %s/xray，拒绝覆盖；请核对已有安装或选择新目录。\n' "$client_dir" >&2
  exit 1
fi
# Keep both partial and verified archives across runs, separately by version/arch.
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/xray-client/v${XRAY_VERSION}"
mkdir -p -- "$cache_dir"
chmod 700 -- "$cache_dir"
archive_file="$cache_dir/$archive"
for cache_file in "$archive_file" "$archive_file.lock"; do
  if [[ -L "$cache_file" || ( -e "$cache_file" && ! -f "$cache_file" ) ]]; then
    printf '缓存路径不是普通文件：%s\n' "$cache_file" >&2
    exit 1
  fi
done
# Python locks the inherited descriptor; Bash keeps it open until installation exits.
# Leave the lock file in place so concurrent runs always lock the same inode.
exec 9>"$archive_file.lock"
python3 - <<'PY'
import fcntl, sys
try:
    fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit('另一个安装进程正在使用此下载缓存，请等待它完成。')
PY
archive_ok() {
  [[ -f "$archive_file" ]] &&
    printf '%s  %s\n' "$expected_sha256" "$archive_file" | sha256sum --check --status -
}
interrupted() {
  printf '\n安装已中断，下载缓存已保留；重新运行相同命令即可继续。\n' >&2
  exit "$1"
}
trap 'interrupted 130' INT
trap 'interrupted 143' TERM
trap 'interrupted 129' HUP
printf '下载缓存：%s\n' "$archive_file"
if archive_ok; then
  printf '缓存已通过 SHA-256 校验，跳过下载。\n'
else
  for attempt in 1 2 3 4; do
    printf '下载 Xray %s（第 %s/4 次尝试，自动续传已有内容）\n' "$XRAY_VERSION" "$attempt"
    curl_status=0
    # Retry with a new curl process so each attempt resumes from the latest size.
    http_code="$(curl --disable --fail --location --continue-at - \
      --connect-timeout 15 --max-time 1800 --speed-limit 1024 --speed-time 120 \
      --proto '=https' --proto-redir '=https' --tlsv1.2 \
      --write-out '%{http_code}' \
      "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/${archive}" \
      --output "$archive_file")" || curl_status=$?
    if archive_ok; then
      break
    fi
    # Some curl versions treat HTTP 416 as success even with --fail.
    # An unverified cache still needs a fresh download in that case.
    if [[ "$http_code" == 416 ]] && (( curl_status == 0 )); then
      curl_status=33
    fi
    if (( curl_status == 0 )); then
      rm -f -- "$archive_file"
      printf 'SHA-256 校验失败，已删除损坏的缓存，拒绝安装；请重新运行。\n' >&2
      exit 1
    fi
    if (( attempt == 4 )); then
      printf '下载未完成，缓存已保留；重新运行相同命令即可续传。\n' >&2
      exit "$curl_status"
    fi
    if (( curl_status == 33 )) || [[ "$http_code" == 416 ]]; then
      printf '下载源无法续传当前缓存，将重新完整下载。\n' >&2
      rm -f -- "$archive_file"
    else
      case "$curl_status:$http_code" in
        5:*|6:*|7:*|18:*|28:*|35:*|52:*|55:*|56:*|92:*|22:408|22:429|22:500|22:502|22:503|22:504)
          printf '网络中断或暂时不可用，保留进度后重试。\n' >&2 ;;
        *)
          printf '下载失败（curl %s），缓存已保留；解决错误后重新运行即可续传。\n' "$curl_status" >&2
          exit "$curl_status" ;;
      esac
    fi
    sleep "$attempt"
  done
fi

# Only extraction uses a temporary directory; never remove the download on exit.
download_dir="$(mktemp -d -t xray-client-extract.XXXXXXXX)"
cleanup() {
  rm -f -- "$download_dir/xray"
  rmdir -- "$download_dir"
}
trap cleanup EXIT
python3 - "$archive_file" "$download_dir/xray" <<'PY'
import pathlib, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    pathlib.Path(sys.argv[2]).write_bytes(archive.read('xray'))
PY
chmod 755 "$download_dir/xray"
"$download_dir/xray" version
mkdir -p -- "$client_dir"
install -m 755 -- "$download_dir/xray" "$client_dir/xray"
printf '已安装固定版本 Xray %s：%s/xray\n' "$XRAY_VERSION" "$client_dir"
printf '下一步：从服务器复制 .runtime/client.json，按项目根目录 README.md 的 Linux 命令行客户端章节启动。\n'
