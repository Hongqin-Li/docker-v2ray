#!/usr/bin/env python3
"""Isolated VLESS / REALITY / Vision deployment; Python standard library only."""

import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode, urlsplit
import uuid


BASE = Path(__file__).resolve().parent
STATE = BASE / ".runtime"
PROJECT = "docker-v2ray-xray"
VERSION = "26.3.27"
REPOSITORY = "ghcr.io/xtls/xray-core"
# Official multi-platform manifest, resolved and tested on 2026-09-30.
# Do not replace this with a mutable tag or an automatic latest-release lookup.
IMAGE = REPOSITORY + "@sha256:592ec4d11f656db95598d01e76dbcc6e002d67360b96a5436500a938230f52c7"
PRIVATE_IPS = [
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4",
    "240.0.0.0/4", "::/128", "::1/128", "fc00::/7", "fe80::/10", "ff00::/8",
]


def fail(message):
    raise RuntimeError(message)


def run(args, capture=False, timeout=120, env=None):
    result = subprocess.run(
        [str(x) for x in args], text=True, stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None, timeout=timeout, env=env,
    )
    if result.returncode:
        # Do not echo command arguments: key-generation commands can contain secrets.
        if capture and result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        fail("命令执行失败（退出码 {}）：{}".format(result.returncode, args[0]))
    return result.stdout.strip() if capture else ""


def prerequisites():
    if shutil.which("docker") is None:
        fail("需要先安装 Docker Engine 和 Docker Compose 插件。")
    run(["docker", "info", "--format", "{{.ServerVersion}}"], capture=True, timeout=20)
    run(["docker", "compose", "version"], capture=True, timeout=20)


def own_containers():
    ids = run([
        "docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + PROJECT,
    ], capture=True).split()
    if not ids:
        return []
    containers = json.loads(run(["docker", "inspect", *ids], capture=True))
    for item in containers:
        labels = item["Config"].get("Labels") or {}
        workdir = labels.get("com.docker.compose.project.working_dir", "")
        if not workdir or Path(workdir).resolve() != BASE:
            fail("同名 Compose 项目属于其他目录，拒绝操作：" + PROJECT)
    return containers


def compose(*args, capture=False):
    environment = os.environ.copy()
    for name in ("XRAY_IMAGE", "XRAY_LISTEN_IP", "XRAY_PORT"):
        environment.pop(name, None)
    return run([
        "docker", "compose", "--project-name", PROJECT,
        "--project-directory", BASE, "--env-file", STATE / "deploy.env",
        "-f", BASE / "compose.yaml", *args,
    ], capture=capture, timeout=None if "--follow" in args else 180, env=environment)


def host(value):
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    if len(value) > 253 or not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value
    ) or any(not x or len(x) > 63 or x.startswith("-") or x.endswith("-")
             for x in value.split(".")):
        raise argparse.ArgumentTypeError("请填写 IP 或域名，不要包含协议、路径或端口。")
    return value


def port(value):
    try:
        result = int(value)
        if 1 <= result <= 65535:
            return result
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("端口必须在 1 到 65535 之间。")


def target_address(value):
    try:
        parsed = urlsplit("//" + value)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError()
        if not parsed.hostname or not parsed.port:
            raise ValueError()
        return host(parsed.hostname), port(str(parsed.port))
    except (ValueError, argparse.ArgumentTypeError):
        fail("REALITY target 必须是 域名:端口、IPv4:端口 或 [IPv6]:端口。")


def check_target(sni, target):
    address, target_port = target_address(target)
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(["h2"])
    with socket.create_connection((address, target_port), timeout=12) as sock:
        with context.wrap_socket(sock, server_hostname=sni) as secure:
            if secure.version() != "TLSv1.3" or secure.selected_alpn_protocol() != "h2":
                fail("目标网站需要支持 TLS 1.3 和 h2，请另选目标。")
    print("REALITY 目标检查通过：TLS 1.3 / h2 / 证书域名匹配。")


def port_available(address, listen_port):
    # IPv4-only host bind is intentional; the remote server address can be IPv6.
    ids = run(["docker", "ps", "-q"], capture=True).split()
    containers = json.loads(run(["docker", "inspect", *ids], capture=True)) if ids else []
    for item in containers:
        bindings = item.get("NetworkSettings", {}).get("Ports", {}) or {}
        for container_port, entries in bindings.items():
            if container_port.endswith("/tcp") and any(
                int(entry["HostPort"]) == listen_port for entry in entries or []
            ):
                fail("TCP 端口 {} 已由容器 {} 发布。".format(listen_port, item["Name"]))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # A recently stopped listener may leave TIME_WAIT connections behind.
        # Docker also uses SO_REUSEADDR; these are not active port owners.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((address, listen_port))
        except OSError as exc:
            fail("TCP 端口 {}:{} 不可用：{}".format(address, listen_port, exc))


def xray(image, *args, config=None, capture=False):
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--log-driver", "none", "--tmpfs", "/usr/local/etc/xray:rw,size=1m",
        "--tmpfs", "/var/log/xray:rw,size=1m",
    ]
    if config is not None:
        command += ["--mount", "type=bind,src={},dst=/etc/xray/config.json,readonly".format(config)]
    command += [image, *args]
    return run(command, capture=capture, timeout=60)


def write_json(path, value, mode=0o600):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    path.chmod(mode)


def config_test(directory, image):
    for name in ("server.json", "client.json"):
        source = directory / name
        # The host state directory stays 0700. The non-root container only sees
        # this one read-only bind mount, not the directory or other credentials.
        original = source.stat().st_mode & 0o777
        source.chmod(0o644)
        try:
            xray(image, "run", "-test", "-config", "/etc/xray/config.json", config=source)
        finally:
            source.chmod(original)


def initialize(args):
    if STATE.exists():
        fail(".runtime 已存在，拒绝覆盖 UUID、密钥及配置。请使用 up/check/status。")
    if own_containers():
        fail("项目容器已经存在；请先核对配置目录，不能重新初始化。")
    try:
        ipaddress.IPv4Address(args.listen_ip)
    except ValueError:
        fail("--listen-ip 需要填写本机 IPv4 地址，例如 0.0.0.0 或 127.0.0.1。")
    if args.http_port == args.socks_port:
        fail("客户端 HTTP 和 SOCKS 端口不能相同。")
    target = args.target or args.sni + ":443"
    port_available(args.listen_ip, args.port)
    check_target(args.sni, target)
    image = IMAGE
    run(["docker", "pull", image], timeout=300)
    key_output = xray(image, "x25519", capture=True)
    private = re.search(r"(?im)^Private\s*Key:\s*(\S+)", key_output)
    public = re.search(r"(?im)^(?:Public\s*Key|Password(?:\s*\(PublicKey\))?):\s*(\S+)", key_output)
    if not private or not public:
        fail("无法解析 xray x25519 的输出；没有写入配置。")
    private, public = private.group(1), public.group(1)
    if not all(re.fullmatch(r"[A-Za-z0-9_-]{43}", value) for value in (private, public)):
        fail("REALITY 密钥格式异常；没有写入配置。")
    user_id, short_id = str(uuid.uuid4()), secrets.token_hex(8)
    server = {
        "log": {"loglevel": "warning", "access": "none"},
        "inbounds": [{
            "tag": "reality-in", "listen": "0.0.0.0", "port": 8443,
            "protocol": "vless", "settings": {
                "clients": [{"id": user_id, "flow": "xtls-rprx-vision"}],
                "decryption": "none",
            },
            "streamSettings": {"network": "raw", "security": "reality", "realitySettings": {
                "show": False, "target": target, "xver": 0,
                "serverNames": [args.sni], "privateKey": private, "shortIds": [short_id],
            }},
        }],
        "outbounds": [{"tag": "direct", "protocol": "freedom"},
                      {"tag": "block", "protocol": "blackhole"}],
        "routing": {"domainStrategy": "IPOnDemand", "rules": [
            {"type": "field", "ip": PRIVATE_IPS, "outboundTag": "block"},
        ]},
    }
    client = {
        "log": {"loglevel": "warning", "access": "none"},
        "inbounds": [
            {"tag": "http-in", "listen": "127.0.0.1", "port": args.http_port,
             "protocol": "http", "settings": {}},
            {"tag": "socks-in", "listen": "127.0.0.1", "port": args.socks_port,
             "protocol": "socks", "settings": {"auth": "noauth", "udp": True}},
        ],
        "outbounds": [{
            "tag": "proxy", "protocol": "vless", "settings": {"vnext": [{
                "address": args.server, "port": args.port, "users": [{
                    "id": user_id, "encryption": "none", "flow": "xtls-rprx-vision",
                }],
            }]},
            "streamSettings": {"network": "raw", "security": "reality", "realitySettings": {
                "fingerprint": "chrome", "serverName": args.sni,
                "publicKey": public, "shortId": short_id, "spiderX": "/",
            }},
            "mux": {"enabled": False},
        }],
    }
    endpoint = "[{}]".format(args.server) if ":" in args.server else args.server
    query = urlencode({
        "encryption": "none", "security": "reality", "type": "tcp",
        "flow": "xtls-rprx-vision", "sni": args.sni, "fp": "chrome",
        "pbk": public, "sid": short_id, "spx": "/",
    })
    link = "vless://{}@{}:{}?{}#xray-reality\n".format(user_id, endpoint, args.port, query)
    metadata = {
        "version": VERSION, "image": image, "project": PROJECT,
        "server": args.server, "port": args.port, "listen_ip": args.listen_ip,
        "sni": args.sni, "target": target,
        "http_port": args.http_port, "socks_port": args.socks_port,
    }
    temporary = Path(tempfile.mkdtemp(prefix=".init-", dir=str(BASE)))
    try:
        write_json(temporary / "server.json", server, 0o644)
        write_json(temporary / "client.json", client)
        write_json(temporary / "metadata.json", metadata)
        (temporary / "node.txt").write_text(link)
        (temporary / "deploy.env").write_text(
            "XRAY_IMAGE={}\nXRAY_LISTEN_IP={}\nXRAY_PORT={}\n".format(image, args.listen_ip, args.port)
        )
        config_test(temporary, image)
        # No --force path: existing credentials can never be silently replaced.
        temporary.rename(STATE)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print("初始化成功；尚未启动监听。配置目录：" + str(STATE))
    print("下一步：./deploy.sh up；客户端说明：项目根目录 README.md 的各平台客户端章节")


def load_metadata():
    if not (STATE / "metadata.json").is_file():
        fail("尚未初始化，请先执行 ./deploy.sh init --help。")
    metadata = json.loads((STATE / "metadata.json").read_text())
    if metadata["version"] != VERSION or metadata["image"] != IMAGE:
        fail("配置记录的版本与脚本固定版本不一致，请先完成显式升级/回退检查。")
    expected_env = "XRAY_IMAGE={}\nXRAY_LISTEN_IP={}\nXRAY_PORT={}\n".format(
        IMAGE, metadata["listen_ip"], metadata["port"])
    if (STATE / "deploy.env").read_text() != expected_env:
        fail("deploy.env 与初始化记录不一致，拒绝使用可能漂移的镜像或端口。")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="独立部署 VLESS + REALITY + Vision，不操作原有 V2Ray 项目。")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="生成凭据和配置；不会启动服务；已有配置时拒绝覆盖")
    init.add_argument("--server", required=True, type=host, help="客户端连接的 VPS 公网 IP 或域名")
    init.add_argument("--sni", required=True, type=host, help="REALITY 目标网站域名，无需拥有该域名")
    init.add_argument("--target", help="目标地址（默认 SNI:443）；可以选与 SNI 匹配的 IP:443")
    init.add_argument("--port", type=port, default=8443, help="服务端 TCP 端口，默认 8443")
    init.add_argument("--listen-ip", default="0.0.0.0", help="宿主机 IPv4 监听地址，默认 0.0.0.0")
    init.add_argument("--http-port", type=port, default=1187, help="生成的客户端 HTTP 端口，默认 1187")
    init.add_argument("--socks-port", type=port, default=1180, help="生成的客户端 SOCKS 端口，默认 1180")
    for command, help_text in (
        ("up", "校验并启动本目录的 Xray 容器"),
        ("down", "停止并移除本目录的 Xray 容器，保留配置"),
        ("check", "检查两端配置及 REALITY 目标可用性"),
        ("status", "显示本项目容器状态及监听端口"),
        ("link", "输出含凭据的 VLESS 导入链接，请勿公开"),
    ):
        commands.add_parser(command, help=help_text)
    logs = commands.add_parser("logs", help="查看本项目最近 100 行日志")
    logs.add_argument("--follow", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if args.command in ("init", "up", "down", "check"):
        lock = (BASE / ".deploy.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("已有部署命令正在执行，请等待该命令完成。")
    if args.command == "link":
        load_metadata()
        print((STATE / "node.txt").read_text(), end="")
        return
    prerequisites()
    own_containers()
    if args.command == "init":
        initialize(args)
        return
    metadata = load_metadata()
    if args.command == "check":
        compose("config", "--quiet")
        config_test(STATE, metadata["image"])
        check_target(metadata["sni"], metadata["target"])
    elif args.command == "up":
        compose("config", "--quiet")
        config_test(STATE, metadata["image"])
        running = any(item["State"]["Running"] for item in own_containers())
        if not running:
            port_available(metadata["listen_ip"], metadata["port"])
        compose("up", "-d", "--pull", "never")
        ready = False
        previous_started = None
        address = "127.0.0.1" if metadata["listen_ip"] == "0.0.0.0" else metadata["listen_ip"]
        for _ in range(10):
            time.sleep(1)
            items = own_containers()
            started = [x["State"]["StartedAt"] for x in items]
            if items and all(x["State"]["Running"] and not x["State"]["Restarting"] for x in items):
                try:
                    with socket.create_connection((address, metadata["port"]), timeout=1):
                        ready = started == previous_started
                except OSError:
                    pass
            previous_started = started
            if ready:
                break
        if not ready:
            fail("容器未稳定启动或端口不可达；请执行 ./deploy.sh logs 查看原因。")
        print("Xray 已启动：TCP {}:{}。请按客户端文档验证实际代理访问。".format(
            metadata["listen_ip"], metadata["port"]))
    elif args.command == "down":
        compose("down")
        print("Xray 项目已停止；.runtime 中的配置和凭据保留。")
    elif args.command == "status":
        print("Xray {} / TCP {}:{}".format(metadata["version"], metadata["listen_ip"], metadata["port"]))
        compose("ps", "-a")
    elif args.command == "logs":
        compose("logs", "--tail", "100", *(["--follow"] if args.follow else []))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("错误：" + str(exc), file=sys.stderr)
        sys.exit(1)
