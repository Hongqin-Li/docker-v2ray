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
download_dir="$(mktemp -d -t xray-client-download.XXXXXXXX)"
cleanup() {
  rm -f -- "$download_dir/archive.zip" "$download_dir/xray"
  rmdir -- "$download_dir"
}
trap cleanup EXIT
curl --fail --location --retry 3 --connect-timeout 15 --max-time 300 \
  --proto '=https' --tlsv1.2 \
  "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/${archive}" \
  --output "$download_dir/archive.zip"
printf '%s  %s\n' "$expected_sha256" "$download_dir/archive.zip" | sha256sum --check -
python3 - "$download_dir/archive.zip" "$download_dir/xray" <<'PY'
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
