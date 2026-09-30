#!/usr/bin/env bash
# Bootstrap dependencies only; never initialize Xray or restart an active Docker.
set -Eeuo pipefail

log() { printf '[xray-deps] %s\n' "$*"; }
die() { printf '[xray-deps] 错误：%s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
    cat <<'EOF'
用法：bash install-deps.sh [--check | --dry-run | --help]
  默认        自动安装缺失依赖；非 root 用户自动通过 sudo 执行。
  --check     只检查，缺少依赖时退出码为 1；不安装、不启动服务。
  --dry-run   显示安装计划，不修改系统；不需要 root。
支持 Ubuntu 20.04/22.04/24.04/26.04、Debian 11/12/13，amd64/arm64。
已有可用 Docker / Compose 直接复用；全新安装使用脚本内固定版本。
EOF
}

select_platform() {
    OS_ID=$1 OS_VERSION=$2 ARCH=$3
    case "$OS_ID:$OS_VERSION" in
        ubuntu:20.04) CODENAME=focal ;;
        ubuntu:22.04) CODENAME=jammy ;;
        ubuntu:24.04) CODENAME=noble ;;
        ubuntu:26.04) CODENAME=resolute ;;
        debian:11) CODENAME=bullseye ;;
        debian:12) CODENAME=bookworm ;;
        debian:13) CODENAME=trixie ;;
        *) die "不支持 $OS_ID $OS_VERSION；支持的系统见 --help，未修改软件源。" ;;
    esac
    case "$ARCH" in
        amd64) COMPOSE_ARCH=x86_64
            COMPOSE_SHA256=7bdb2ce2916e5dd0354e5d129892bf96fdcdb1a9ab8eed69b9173e131db4c230 ;;
        arm64) COMPOSE_ARCH=aarch64
            COMPOSE_SHA256=a91e930a076b91e6c69f11d1dbe3c06729ae765fb9dbb3f97cb808e784647399 ;;
        *) die "不支持架构 $ARCH；只支持 amd64 / arm64。" ;;
    esac
    # Exact versions verified against Docker's signed APT repositories.
    local suffix="-1~${OS_ID}.${OS_VERSION}~${CODENAME}"
    ENGINE_VERSION="5:29.6.2${suffix}"
    CONTAINERD_VERSION="2.2.6${suffix}"
    COMPOSE_PACKAGE_VERSION="5.3.1${suffix}"
    if [[ $CODENAME == focal ]]; then
        ENGINE_VERSION="5:28.1.1${suffix}"
        CONTAINERD_VERSION=1.7.27-1
        COMPOSE_PACKAGE_VERSION="2.35.1${suffix}"
    fi
    # For existing Docker installations, add only this checksum-pinned plugin.
    COMPOSE_BINARY_VERSION=2.35.1
    DOCKER_PACKAGES=("docker-ce=$ENGINE_VERSION" "docker-ce-cli=$ENGINE_VERSION"
        "containerd.io=$CONTAINERD_VERSION" "docker-compose-plugin=$COMPOSE_PACKAGE_VERSION")
}

detect_platform() {
    [[ -r /etc/os-release ]] || die "无法读取 /etc/os-release。"
    local ID= VERSION_ID=
    # shellcheck source=/dev/null
    . /etc/os-release
    have dpkg && have apt-get || die "此安装器需要 Debian / Ubuntu 的 APT。"
    [[ $ID != debian ]] || VERSION_ID=${VERSION_ID%%.*}
    select_platform "$ID" "$VERSION_ID" "$(dpkg --print-architecture)"
}

python_ready() {
    have python3 && python3 -c 'import sys, ssl; sys.exit(not (
        sys.version_info >= (3, 8) and ssl.HAS_TLSv1_3 and ssl.HAS_ALPN))' 2>/dev/null
}

probe_base() {
    BASE_PACKAGES=()
    python_ready || BASE_PACKAGES+=(python3)
    have curl || BASE_PACKAGES+=(curl)
    have git || BASE_PACKAGES+=(git)
    [[ -s /etc/ssl/certs/ca-certificates.crt ]] || BASE_PACKAGES+=(ca-certificates)
    if ! have sha256sum || ! have timeout; then BASE_PACKAGES+=(coreutils); fi
}

bounded() {
    if have timeout; then timeout 25 "$@"; else "$@"; fi
}

version_at_least() {
    local value=$1 major=$2 minor=$3
    [[ $value =~ ^v?([0-9]+)\.([0-9]+) ]] || return 1
    (( BASH_REMATCH[1] > major || (BASH_REMATCH[1] == major && BASH_REMATCH[2] >= minor) ))
}

probe_docker() {
    DOCKER_STATE=absent COMPOSE_STATE=absent DOCKER_VERSION= COMPOSE_VERSION=
    DOCKER_ENDPOINT=unix:///var/run/docker.sock
    have docker || return 0
    # Never install/manage a daemon selected through a remote Docker context.
    if [[ -n ${DOCKER_CONTEXT:-} ]]; then
        DOCKER_ENDPOINT=$(docker context inspect "$DOCKER_CONTEXT" --format '{{.Endpoints.docker.Host}}' 2>/dev/null) ||
            die "无法读取 Docker context；请先修复已有 Docker 配置。"
    elif [[ -n ${DOCKER_HOST:-} ]]; then
        DOCKER_ENDPOINT=$DOCKER_HOST
    else
        DOCKER_ENDPOINT=$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null) ||
            die "无法读取 Docker context；请先修复已有 Docker 配置。"
    fi
    [[ $DOCKER_ENDPOINT == unix://* ]] || die "请使用本机 Docker context；不管理远程 Docker。"
    DOCKER_STATE=stopped
    if DOCKER_VERSION=$(bounded docker info --format '{{.ServerVersion}}' 2>/dev/null); then
        version_at_least "$DOCKER_VERSION" 20 10 || die "已有 Docker $DOCKER_VERSION 过旧，需要 20.10+；请单独升级。"
        DOCKER_STATE=ready
    fi
    if COMPOSE_VERSION=$(bounded docker compose version --short 2>/dev/null); then
        version_at_least "$COMPOSE_VERSION" 2 0 || die "已有 Compose $COMPOSE_VERSION 过旧，需要 v2+。"
        COMPOSE_STATE=ready
        if [[ $DOCKER_STATE == ready ]]; then
            bounded docker compose ls --format json >/dev/null 2>&1 ||
                die "已有 Compose 无法访问 Docker；请检查 Docker 权限、API 版本或 context。"
        fi
    fi
}

package_installed() {
    [[ $(dpkg-query -W -f='${Status}' "$1" 2>/dev/null || true) == 'install ok installed' ]]
}

check_fresh_install() {
    local name conflicts=()
    for name in docker.io docker-ce docker-ce-cli docker-engine podman-docker containerd containerd.io runc; do
        package_installed "$name" && conflicts+=("$name")
    done
    ((${#conflicts[@]} == 0)) || die "检测到已有容器组件（${conflicts[*]}），但 docker 命令不可用；请先修复，不自动替换或卸载。"
    if have dockerd || have containerd || have podman; then
        die "发现已有容器运行时；请先确认安装状态，不自动替换。"
    fi
    [[ -d /run/systemd/system ]] && have systemctl || die "自动安装 Docker 需要以 systemd 启动的 VPS。"
}

check_stopped_docker() {
    [[ $DOCKER_ENDPOINT == unix:///var/run/docker.sock || $DOCKER_ENDPOINT == unix:///run/docker.sock ]] ||
        die "当前本机 Docker socket 不可用；请先启动对应的 rootless / 自定义 Docker。"
    [[ -d /run/systemd/system ]] && have systemctl || die "Docker 不可访问；需要管理员先启动本机 Docker。"
    [[ $(systemctl show docker.service -p LoadState --value) == loaded ]] || die "已有 Docker 没有可用的 systemd 服务；请先修复。"
    local state
    state=$(systemctl show docker.service -p ActiveState --value)
    case "$state" in
        inactive|failed) ;;
        *) die "Docker 服务状态为 $state，但 API 不可访问；请检查权限或服务日志，不自动重启。" ;;
    esac
}

print_plan() {
    log "系统：$OS_ID $OS_VERSION ($CODENAME)，$ARCH"
    if ((${#BASE_PACKAGES[@]})); then
        log "补齐系统包：${BASE_PACKAGES[*]}（使用发行版软件源，无需 pip）。"
    else
        log "Python、curl、git、CA 证书和基础工具已就绪。"
    fi
    case "$DOCKER_STATE" in
        ready) log "复用 Docker $DOCKER_VERSION，保持现有服务运行。" ;;
        stopped) log "检测到已有 Docker，将尝试启动其停止的本机服务。" ;;
        absent) log "新装固定版本：${DOCKER_PACKAGES[*]}" ;;
    esac
    if [[ $COMPOSE_STATE == ready ]]; then
        log "复用 Docker Compose $COMPOSE_VERSION。"
    elif [[ $DOCKER_STATE != absent ]]; then
        log "仅补装 Compose $COMPOSE_BINARY_VERSION 插件（校验 SHA-256）。"
    fi
}

apt_run() {
    # Prevent needrestart from restarting services after installing base packages.
    DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get \
        -o DPkg::Lock::Timeout=120 -o Acquire::Retries=3 \
        -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 "$@"
}

apt_update() {
    # Reject incomplete indexes rather than silently accepting a failed mirror.
    apt_run -o APT::Update::Error-Mode=any update
}

download() {
    curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 20 --max-time 300 --retry 3 --output "$2" "$1"
}

setup_docker_repo() {
    local url="https://download.docker.com/linux/$OS_ID"
    local key=/etc/apt/keyrings/xray-docker.asc
    local source=/etc/apt/sources.list.d/xray-docker.list
    local existing
    # Reuse an administrator's Docker source, including deb822 .sources files.
    existing=$(grep -lE '^[[:space:]]*(deb[[:space:]]|URIs:[[:space:]])[^#]*https?://download\.docker\.com/linux/' \
        /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true)
    if [[ -n $existing ]]; then
        log "复用已有 Docker 软件源。"
        return
    fi
    [[ ! -e $source && ! -L $source ]] || die "$source 已存在；不覆盖已有软件源。"
    download "$url/gpg" "$WORK_DIR/docker.asc"
    grep -q '^-----BEGIN PGP PUBLIC KEY BLOCK-----' "$WORK_DIR/docker.asc" || die "下载的 Docker 签名公钥格式不正确。"
    install -d -m 0755 /etc/apt/keyrings
    if [[ -e $key || -L $key ]]; then
        [[ ! -L $key ]] && cmp -s "$WORK_DIR/docker.asc" "$key" || die "$key 与官方公钥不同；不覆盖已有文件。"
    else
        install -m 0644 "$WORK_DIR/docker.asc" "$key"
    fi
    printf 'deb [arch=%s signed-by=%s] %s %s stable\n' "$ARCH" "$key" "$url" "$CODENAME" > "$WORK_DIR/docker.list"
    install -m 0644 "$WORK_DIR/docker.list" "$source"
}

check_pinned_packages() {
    local spec package version found
    for spec in "${DOCKER_PACKAGES[@]}"; do
        package=${spec%%=*} version=${spec#*=}
        found=$(apt-cache madison "$package" | awk -v wanted="$version" '$3 == wanted { found=$3 } END { print found }')
        [[ $found == "$version" ]] || die "当前软件源缺少固定包 $spec；请检查软件源/网络，不回退到 latest。"
    done
}

install_docker() {
    setup_docker_repo
    apt_update
    check_pinned_packages
    apt_run install -y --no-install-recommends --no-remove "${DOCKER_PACKAGES[@]}"
    systemctl enable docker.service
    # The package may already have started it. Never restart a running daemon.
    if ! bounded docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
        systemctl start docker.service
    fi
}

install_compose() {
    local directory=${1:-/usr/local/lib/docker/cli-plugins}
    local target=$directory/docker-compose
    [[ ! -e $target && ! -L $target ]] || die "$target 已存在但插件检查失败；不覆盖，请先修复。"
    local binary="$WORK_DIR/docker-compose"
    download "https://github.com/docker/compose/releases/download/v${COMPOSE_BINARY_VERSION}/docker-compose-linux-${COMPOSE_ARCH}" "$binary"
    printf '%s  %s\n' "$COMPOSE_SHA256" "$binary" | sha256sum --check --status || die "Compose SHA-256 不匹配，未安装。"
    chmod 0755 "$binary"
    "$binary" version --short >/dev/null || die "Compose 二进制无法在此系统运行，未安装。"
    install -d -m 0755 "$directory"
    # Copy to a temporary file on the destination filesystem, then link without overwrite.
    local staging
    staging=$(mktemp "$directory/.xray-compose.XXXXXX")
    if install -m 0755 "$binary" "$staging" && ln -T "$staging" "$target"; then
        rm -f "$staging"
    else
        rm -f "$staging"
        die "无法安装 Compose 插件，未覆盖已有文件。"
    fi
}

ensure_root() {
    if [[ $EUID != 0 ]]; then
        have sudo || die "请以 root 运行，或由管理员安装 sudo 后重试。"
        log "安装依赖需要管理员权限，使用 sudo 继续。"
        exec sudo -- bash "$(realpath "${BASH_SOURCE[0]}")" "$@"
    fi
}

main() {
    local mode=install
    case "${1:-}" in
        '') ;;
        --check) mode=check ;;
        --dry-run) mode=dry-run ;;
        --help|-h) usage; return ;;
        *) usage >&2; exit 2 ;;
    esac
    (($# <= 1)) || die "一次只接受一个选项。"
    detect_platform
    if [[ $mode == install ]]; then ensure_root "$@"; fi
    probe_base
    probe_docker
    print_plan
    if [[ $mode == check ]]; then
        ((${#BASE_PACKAGES[@]} == 0)) && [[ $DOCKER_STATE == ready && $COMPOSE_STATE == ready ]] ||
            die "依赖未就绪；请运行 bash install-deps.sh 自动补齐。"
        log "检查通过。"
        return
    fi
    case "$DOCKER_STATE" in
        absent) check_fresh_install ;;
        stopped) check_stopped_docker ;;
    esac
    if [[ $mode == dry-run ]]; then log "以上为计划，未修改系统。"; return; fi
    if ((${#BASE_PACKAGES[@]} == 0)) && [[ $DOCKER_STATE == ready && $COMPOSE_STATE == ready ]]; then
        log "全部依赖已就绪，无需安装。"
        return
    fi
    WORK_DIR=$(mktemp -d /tmp/xray-deps.XXXXXX)
    trap 'rm -rf -- "$WORK_DIR"' EXIT
    if ((${#BASE_PACKAGES[@]})); then
        apt_update
        apt_run install -y --no-install-recommends --no-remove "${BASE_PACKAGES[@]}"
        hash -r
        probe_base
        ((${#BASE_PACKAGES[@]} == 0)) || die "依赖仍不可用：${BASE_PACKAGES[*]}；检查 PATH 是否被自定义旧版 Python 等程序遮蔽。"
    fi
    case "$DOCKER_STATE" in
        absent) install_docker ;;
        stopped) systemctl start docker.service ;;
    esac
    probe_docker
    [[ $DOCKER_STATE == ready ]] || die "Docker 启动后仍不可访问；检查 systemctl status docker，不自动重启。"
    if [[ $COMPOSE_STATE != ready ]]; then install_compose; fi
    probe_docker
    [[ $COMPOSE_STATE == ready ]] || die "Compose 仍不可用；检查用户目录中是否有其他插件遮蔽系统插件。"
    log "依赖安装完成：$(python3 --version)，Docker $DOCKER_VERSION，Compose $COMPOSE_VERSION。"
    log "接下来在 xray 目录运行 ./deploy.sh init --server YOUR_SERVER_IP --port 8443 --sni www.amazon.com"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    trap 'code=$?; printf "[xray-deps] 第 %s 行执行失败（退出码 %s）；解决上方错误后可重新运行。\n" "$LINENO" "$code" >&2; exit "$code"' ERR
    main "$@"
fi
