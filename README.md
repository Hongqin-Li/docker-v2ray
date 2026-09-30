# V2Ray / Xray Quick Start

本项目提供两套独立部署方式，使用说明统一放在本文。Xray 的脚本在 `xray/` 下；原有 Docker V2Ray 的说明保留在本文后半部分。

| 方案 | 协议 | 自有域名 / 证书 | 部署入口 |
| --- | --- | --- | --- |
| Xray | VLESS + TCP + REALITY + Vision | 不需要，可以直接连接 VPS 公网 IP | [快速开始](#xray-start) |
| 原有 V2Ray | VMess + WebSocket + TLS | 需要域名及匹配证书 | 本文后半部分的 `run.sh` 说明 |

Xray 导航：[服务端](#xray-start) · [依赖安装](#xray-deps) · [客户端推荐](#各平台客户端推荐) · [Linux 命令行](#xray-linux) · [各平台 DNS](#xray-dns) · [版本](#xray-versions) · [验证范围](#xray-validation)

## Xray 服务端与客户端

<a id="xray-start"></a>

### 先安装依赖并启动服务端

在 VPS 上执行，将 `YOUR_SERVER_IP` 换成自己的公网 IP。项目需已放在 `~/docker-v2ray`：

```bash
cd ~/docker-v2ray/xray
bash ./install-deps.sh
./deploy.sh init --server YOUR_SERVER_IP --port 8443 --sni www.amazon.com
./deploy.sh up
./deploy.sh status
```

安装器自动识别系统、架构和现有依赖；缺失时补齐，已经可用时跳过。安装需要 root，普通用户执行时会自动调用 sudo；后续部署也需要有 Docker 权限的用户。支持 Ubuntu **20.04 / 22.04 / 24.04 / 26.04**、Debian **11 / 12 / 13**，amd64 / arm64。只需首次运行 `init`，已有配置时直接 `up`。

服务端默认监听 **TCP 8443**，与旧 V2Ray 服务端的 **TCP 443** 分开。VPS 控制台及主机防火墙需允许所选 TCP 端口；脚本不修改防火墙，遇到端口占用会停止。无需自有域名、证书或 Nginx 转发。

`www.amazon.com` 是可替换的 REALITY 目标 / SNI 示例，不是 VPS 的地址。初始化会检查其证书、TLS 1.3 和 h2，失败时不生成凭据。必要时增加 `--target 域名或IP:443`，证书必须匹配 `--sni`；更换目标后仍要验证真实代理访问。Xray 可能提示非 443 端口的识别风险；8443 用于与旧服务并行，协议切换不保证不会被封锁，也不能改变同一 VPS 的线路质量。

初始化后，在服务器自己的终端执行以下命令获取客户端导入链接：

```bash
cd ~/docker-v2ray/xray
./deploy.sh link
```

输出的 `vless://` 链接含访问凭据，只传给自己的设备。Linux 原生客户端复制生成的 `xray/.runtime/client.json`；其他客户端按下文导入链接。DNS 偏好需要在各客户端单独配置。

<a id="xray-deps"></a>

### 依赖安装与固定版本

只安装依赖时执行 `bash ~/docker-v2ray/xray/install-deps.sh` 即可。安装器适用于使用 systemd 的上述 VPS 系统，检查 Python **3.8+**（含 TLS 1.3 / ALPN）、curl、git、CA 证书、基础工具、Docker 和 Compose；不需要 pip、虚拟环境或 Python Docker SDK。它只准备依赖，`deploy.sh init` 生成配置，`deploy.sh up` 才启动 Xray。

| 全新安装的系统 | Docker Engine / CLI | containerd.io | Compose 插件 |
| --- | --- | --- | --- |
| Ubuntu 20.04 | 28.1.1 | 1.7.27 | 2.35.1 |
| Ubuntu 22.04 / 24.04 / 26.04、Debian 11 / 12 / 13 | 29.6.2 | 2.2.6 | 5.3.1 |

- 已有可访问的 Docker **20.10+** / Compose **v2+** 时直接复用，不升降级；全部依赖就绪时也不更新 APT 索引。
- 全新安装使用 Docker 官方 APT 源和精确包版本，自动配置签名公钥、启动 Docker 并启用开机启动。固定包缺失会停止，不回退到 `latest`。
- 已有 Docker、只缺 Compose 时，安装固定 **2.35.1** 插件到 `/usr/local/lib/docker/cli-plugins/docker-compose`，通过脚本内的 amd64 / arm64 SHA-256 校验后才安装。
- 已运行的 Docker 不重启；已停止且有可用 systemd 服务时尝试启动。遇到旧版、损坏的安装或容器组件冲突会说明原因，不自动卸载运行时。
- Python 等基础工具使用发行版软件包，不编译或替换系统 Python，不整体升级系统、不修改用户组。固定版本约束作用于脚本的新安装过程，不设置全局 `apt-mark hold`。

Ubuntu 20.04、Debian 11 使用官方仓库保留的软件包提供兼容路径；新建 VPS 优先使用较新的受支持版本。未列出的系统或架构会明确报错。VPS 需能访问系统软件源及 `download.docker.com`；单独补装 Compose 还需访问 GitHub Release。下载中断后可重新运行；软件源不可达、自定义旧 Python 遮蔽系统 Python 等问题需按报错修复。

```bash
bash ~/docker-v2ray/xray/install-deps.sh --check    # 全部就绪返回 0，否则返回 1
bash ~/docker-v2ray/xray/install-deps.sh --dry-run  # 只看计划，不安装、不启动服务
```

安装依据：[Docker Ubuntu](https://docs.docker.com/engine/install/ubuntu/)、[Docker Debian](https://docs.docker.com/engine/install/debian/)、[Compose Linux](https://docs.docker.com/compose/install/linux/)、[Compose 2.35.1 发布包](https://github.com/docker/compose/releases/tag/v2.35.1)。

### 服务端常用操作与文件

```bash
cd ~/docker-v2ray/xray
./deploy.sh check           # 两端配置语法 + 目标 TLS 检查
./deploy.sh up              # 启动；已有同配置容器时复用
./deploy.sh status
./deploy.sh logs            # 加 --follow 持续查看
./deploy.sh link            # 显式显示客户端导入链接
./deploy.sh down            # 只移除本项目容器和网络，保留配置及镜像
```

所有容器操作使用 `xray/compose.yaml` 和独立项目名 `docker-v2ray-xray`。同名项目属于其他目录时会拒绝操作，不使用上一级的 `docker-compose.yml`。修改 `server.json` 后需 `down` 再 `up` 才能重新加载，修改认证参数后也要同步客户端；不要重复 `init` 覆盖凭据。日志默认关闭访问记录，警告 / 错误写入 Docker 日志，最多 3 个文件、每个 10 MB。

| 文件 / 目录 | 用途 |
| --- | --- |
| `xray/install-deps.sh` | 自动安装服务端依赖 |
| `xray/deploy.sh`、`xray/deploy.py`、`xray/compose.yaml` | 服务端配置与容器管理 |
| `xray/install-client.sh` | 固定版本的 Linux 客户端安装器 |
| `xray/tests/` | 依赖安装器的隔离分支测试 |
| `xray/.runtime/server.json` | 服务端配置，含私钥 |
| `xray/.runtime/client.json`、`node.txt` | 客户端配置、节点导入链接 |
| `xray/.runtime/metadata.json`、`deploy.env` | 版本、目标、端口及固定镜像记录 |

UUID、REALITY 私钥和 short ID 在初始化时随机生成，不复用旧 V2Ray 认证信息。`.runtime/` 权限为 0700，客户端配置与节点链接为 0600；`server.json` 为 0644，便于容器内非 root 用户只读访问，宿主机其他用户无法穿过父目录读取它。

`.runtime/` 已被 Git 忽略。公开文档只使用 `YOUR_SERVER_IP`、`YOUR_UUID` 等占位符，不提交实际配置、节点链接、二维码或私钥。Codex 账号凭据也不属于代理配置，不应复制到 VPS 或提交仓库。

<a id="xray-versions"></a>

### Xray 版本与兼容性

服务端及 Linux 原生客户端固定 **Xray 26.3.27**。客户端发布包的两种架构 SHA-256 写在安装器中，已有二进制不会被覆盖；服务端使用以下多架构镜像 digest：

```text
ghcr.io/xtls/xray-core@sha256:592ec4d11f656db95598d01e76dbcc6e002d67360b96a5436500a938230f52c7
```

初始化和启动不会查询“最新版本”。升级需显式修改脚本中的版本、镜像 digest 和客户端摘要，并重新验证客户端。官方依据：[Xray 26.3.27](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27)、[Docker 镜像说明](https://github.com/XTLS/Xray-core#installation)、[REALITY 目标要求](https://github.com/XTLS/REALITY)。

iOS 以 **Shadowrocket 2.2.92** 为兼容性参考。当前选择用于避开该版本与 Xray 26.9.9 的[特定握手问题报告](https://github.com/Shadowrocket/config/issues/4)，不启用额外后量子认证，也不设置客户端最低版本；这不代表已经在 iPhone 实测通过。图形客户端自带内核不受本仓库固定版本控制，更新后应重新验证。

### 各平台客户端推荐

| 平台 | 推荐客户端 / 官方下载 | 配置方法 |
| --- | --- | --- |
| Windows | [v2rayN](https://github.com/2dust/v2rayN/releases) | 选择适配 x64 / arm64 等架构的包，使用 Xray 内核，导入 VLESS 链接 |
| macOS | [v2rayN](https://github.com/2dust/v2rayN/releases) | Apple Silicon 选 arm64，Intel 选 x64；导入同一 VLESS 链接 |
| Linux 命令行 | 本项目 [固定版本 Xray 安装器](xray/install-client.sh) | 支持 amd64 / arm64，复制配置并启动，详见 [Linux 说明](#xray-linux) |
| Linux 桌面 | [v2rayN](https://github.com/2dust/v2rayN/releases) | 按发行版和架构选择包，配置方法与 Windows / macOS 一致 |
| Android | [v2rayNG](https://github.com/2dust/v2rayNG/releases) | 导入 VLESS 链接，选择节点并启动 VPN |
| iOS / iPadOS | [Shadowrocket（小火箭）](https://apps.apple.com/us/app/shadowrocket/id932747118) | 从剪贴板导入，核对 REALITY / Vision，允许 VPN；见下文的小火箭步骤 |

桌面与 Android 客户端从项目官方 Release 选择正式版本，并记录应用及内核版本；上表不是自动下载“最新版”的安装脚本。图形客户端自带的内核不受本仓库安装器固定，更新后应重新验证。v2rayN 的系统要求和各安装包区别见其[官方说明](https://github.com/2dust/v2rayN/wiki/Release-files-introduction)，v2rayNG 的使用说明见[官方 Wiki](https://github.com/2dust/v2rayNG/wiki)。

### 所有平台都要核对的节点参数

优先导入脚本生成的链接；手工配置时，对照服务器 `.runtime/client.json` 或链接填写：

| 字段 | 值 |
| --- | --- |
| 协议 / 类型 | `VLESS` |
| 服务器地址 | `YOUR_SERVER_IP`，对应初始化的 `--server` |
| 服务器端口 | `8443`，或初始化时指定的端口 |
| UUID | `YOUR_UUID`，由脚本随机生成 |
| VLESS 加密 | `none` |
| 传输 | TCP；Xray 配置中的 `raw` 表示此传输 |
| 安全层 | `REALITY` |
| Flow / 流控 | `xtls-rprx-vision` |
| SNI / Server Name | 与服务端 `--sni` 一致，例如 `www.amazon.com` |
| Public Key / 公钥 | 链接中的 `pbk`，或客户端配置中的 `publicKey` |
| Short ID | 链接中的 `sid`，或客户端配置中的 `shortId` |
| 指纹 / Fingerprint | `chrome` |
| Mux / Multiplex | 关闭 |

服务器地址填 VPS IP，SNI 填选定的 REALITY 目标域名，两者含义不同。客户端不需要服务端私钥，也不需要 WebSocket 路径、Host 或自行申请的 TLS 证书。

### Windows / macOS / Linux 桌面：v2rayN

1. 安装对应平台的 v2rayN，确认 Xray 内核可用；不要使用旧 V2Ray 4.x 内核运行 REALITY 节点。
2. 复制服务器生成的 `vless://` 链接，在客户端使用“从剪贴板导入”功能，选中该节点作为当前服务器。菜单名称可能随版本变化。
3. 编辑节点并核对上表的 TCP、REALITY、Vision、公钥、Short ID 和 SNI，关闭 Mux。
4. 浏览器可使用客户端提供的系统代理功能；终端程序显式设置进程代理变量。先在客户端设置中查看实际 HTTP / mixed 监听端口，不要把服务端 8443 填为本地代理端口，也不要默认所有 GUI 都使用 1187。
5. 用实际 HTTPS 网站验证，再测试需要使用的应用。若选择规则分流，确保目标应用所用域名被路由到该节点。

### Android：v2rayNG

1. 从官方 Release 安装适配手机 CPU 的 APK；不确定架构时选择该版本提供的通用包（若有）。
2. 复制 `vless://` 链接，通过添加节点的“从剪贴板导入”功能导入，也可扫描在自己设备上生成的节点二维码。
3. 选中节点，核对上表参数，启动连接并允许 Android 的 VPN 请求。
4. 检查应用分流没有排除待测试应用，再打开 HTTPS 网站验证。延迟测试只作辅助。

### iOS / iPadOS：Shadowrocket（小火箭）

1. 安装 Shadowrocket，复制 `vless://` 链接后在应用中从剪贴板导入。
2. 类型选择 **VLESS**，核对 TCP、REALITY、`xtls-rprx-vision`、SNI、Public Key、Short ID，关闭 Mux。
3. 选中节点并开启连接，首次使用允许添加 VPN 配置。先让测试网站明确走代理，验证成功后再按需要配置规则分流。

兼容性参考版本为 **Shadowrocket 2.2.92**，类型选择 VLESS，不是 Shadowsocks。SNI 保持服务端目标域名，不能改为 VPS IP；地址仍填 VPS IP。先完成实际网站访问，再切换规则分流；DNS 另按[小火箭 DNS 设置](#ios-dns)配置。分享排错截图时隐藏地址、UUID、公钥、Short ID 和二维码。

<a id="xray-linux"></a>

### Linux 命令行客户端

先按 [服务端步骤](#xray-start) 在服务器初始化并启动 Xray。此客户端使用独立目录及端口，不需要 root，不替换原有 V2Ray 二进制或 `config2.json`。

以下“本机”指运行 Codex、curl 等应用的 Linux 电脑。Xray 客户端默认在这台电脑的 `127.0.0.1` 上监听 **HTTP 1187 / SOCKS 1180**，供本机应用连接，再由客户端连接 VPS 的 **TCP 8443**。1187 / 1180 与旧客户端的 1087 / 1080 分开，便于两套客户端并行运行；无需在 VPS 防火墙中开放这两个客户端端口。

默认连接关系：

```text
Codex / curl → 127.0.0.1:1187（HTTP）或 :1180（SOCKS5）
            → YOUR_SERVER_IP:8443（VLESS + REALITY + Vision）
            → 目标网站
```

#### 安装固定版本并复制配置

以下命令在本机 Linux 执行。依赖 `bash`、`curl`、`sha256sum`、`python3`、`install`、`scp`。支持 x86_64 和 arm64。

本例显式指定安装目录为 `~/xray-client`，程序为 `~/xray-client/xray`，配置为 `~/xray-client/config.json`。安装脚本的第一个参数就是安装目录；如需换目录，请同步调整下文的配置、启动和后台服务路径。

```bash
mkdir -p ~/xray-client-setup
scp root@YOUR_SERVER_IP:/root/docker-v2ray/xray/install-client.sh ~/xray-client-setup/
bash ~/xray-client-setup/install-client.sh ~/xray-client
scp root@YOUR_SERVER_IP:/root/docker-v2ray/xray/.runtime/client.json \
  ~/xray-client/config.json
chmod 600 ~/xray-client/config.json
```

安装器从官方 release 下载 **26.3.27**，并核对写死的 SHA-256；摘要不匹配则停止。现有 `xray` 文件不会被覆盖。若下载需要代理，可以临时沿用旧客户端：

```bash
HTTPS_PROXY=http://127.0.0.1:1087 bash ~/xray-client-setup/install-client.sh ~/xray-client
```

原来的 V2Ray 4.22.1 不能用于运行本说明中的 REALITY 配置。这里下载的是独立 Xray 客户端。

#### 先前台运行并验证

```bash
cd ~/xray-client
./xray version
./xray run -test -config config.json
./xray run -config config.json
```

保留这个终端，另开终端测试。使用 `--noproxy ''` 避免现有 NO_PROXY 设置让测试绕过代理：

```bash
curl --noproxy '' --proxy http://127.0.0.1:1187 \
  --connect-timeout 10 --max-time 30 https://www.cloudflare.com/cdn-cgi/trace
curl --noproxy '' --proxy socks5h://127.0.0.1:1180 \
  --connect-timeout 10 --max-time 30 https://www.cloudflare.com/cdn-cgi/trace
```

响应中的 `ip=` 应是 VPS 出口地址。SOCKS 使用 `socks5h`，让目标网站的域名通过代理端解析。短请求通过仅说明基本连通，还需用 Codex 实际使用一段时间确认长连接表现。

若客户端本地端口被占用，可修改本机 `config.json` 的两个入站端口，并同步下面的代理环境变量；监听地址保持为 `127.0.0.1`。

#### 后台运行：systemd 用户服务

前台验证后按 Ctrl+C 退出，再创建用户服务。服务文件中的 `%h/xray-client` 对应上面指定的 `~/xray-client`，其中 `%h` 表示当前用户的主目录：

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/xray-client.service <<'EOF'
[Unit]
Description=Xray REALITY client

[Service]
ExecStart=%h/xray-client/xray run -config %h/xray-client/config.json
Restart=on-failure
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now xray-client.service
systemctl --user status xray-client.service --no-pager
```

```bash
journalctl --user -u xray-client.service -n 50 --no-pager
systemctl --user restart xray-client.service
systemctl --user stop xray-client.service
```

若出现 `Failed to connect to bus`，当前环境没有可用的 systemd 用户会话，可使用下面的普通后台方式。用户服务能否在退出登录后继续运行，取决于本机的用户会话/linger 设置。

#### 无 systemd 用户会话时：nohup

不要和前台进程或 systemd 服务同时启动。以下示例在进程仍存在时拒绝重复启动：

```bash
cd ~/xray-client
if test -s xray.pid && kill -0 "$(cat xray.pid)" 2>/dev/null; then
  printf 'PID 文件中的进程仍存在，请先核对进程。\n'
else
  nohup ./xray run -config config.json >xray.log 2>&1 &
  printf '%s\n' "$!" >xray.pid
  sleep 1
  kill -0 "$(cat xray.pid)" 2>/dev/null || tail -n 30 xray.log
fi
```

停止时先核对 PID 指向本目录的 Xray，避免误停其他进程：

```bash
cd ~/xray-client
xray_pid="$(cat xray.pid)"
if test "$(readlink "/proc/$xray_pid/exe")" = "$PWD/xray"; then
  kill "$xray_pid"
  rm -f xray.pid
else
  printf 'PID 已失效或属于其他程序，未执行停止。\n'
fi
```

普通后台方式的 `xray.log` 不自动轮转；长期运行优先使用 systemd 用户服务。客户端默认关闭访问日志，日志级别 warning。

<a id="xray-codex"></a>

#### 给 Codex / 命令行程序使用

先确认新的代理测试通过。只给本次 Codex 进程设置新入口：

```bash
HTTPS_PROXY=http://127.0.0.1:1187 \
HTTP_PROXY=http://127.0.0.1:1187 \
ALL_PROXY=http://127.0.0.1:1187 \
https_proxy=http://127.0.0.1:1187 \
http_proxy=http://127.0.0.1:1187 \
all_proxy=http://127.0.0.1:1187 \
NO_PROXY=localhost,127.0.0.1,::1 \
no_proxy=localhost,127.0.0.1,::1 \
codex
```

环境变量只影响本次进程及其子进程，不会改变已经运行的 Codex，也不写入 `.bashrc`、系统代理或 Codex 配置。大小写变量同时设置，避免继承的旧入口影响不同网络库。`NO_PROXY` 在本次测试中只排除本机；日常使用可追加自己的内网规则，但不能包含 `*`、OpenAI / ChatGPT 或待测目标域名，否则相应请求可能绕过代理。

如需回到旧入口，重新以原有代理环境变量启动即可。桌面 GUI 用户需将 1187 改成实际 HTTP / mixed 端口；HTTPS 请求通过 CONNECT 隧道传输，因此代理地址仍使用 `http://`。这些设置只影响采用代理的请求，系统 DNS 接管见[下文](#xray-dns)。

#### 常见问题

- 配置检查通过但连接超时：确认服务器 `./deploy.sh status` 正常，所选 TCP 端口可达，客户端地址与端口正确。
- REALITY 握手失败：核对 UUID、SNI、publicKey、shortId 和 flow；优先重新复制生成的配置，检查服务器 `./deploy.sh check` 与两端日志。不要通过关闭证书验证来掩盖错误。
- `address already in use`：本机端口已有监听进程，或重复启动了客户端。
- HTTP 403/401：说明可能已到达目标网站，应结合响应与客户端日志判断，不能仅凭状态码认定隧道失败。
- 稳定性仍受同一 VPS 的线路影响，迁移协议不等于更换线路。

<a id="xray-dns"></a>

### 各平台 DNS 也走代理

适用于本项目的 VLESS + REALITY + Vision 客户端。先完成 [服务端部署](#xray-start) 和 [客户端导入](#各平台客户端推荐)，确认节点本身可用，再设置 DNS。

#### 先明确代理范围

| 使用方式 | 域名如何解析 | 覆盖范围 |
| --- | --- | --- |
| HTTP 代理访问 HTTPS 网站 | 应用以域名发出 CONNECT；本项目客户端将域名传给 VPS 解析 | 采用该代理的请求 |
| curl 使用 `socks5h://` | 把域名交给代理；本项目配置继续传给 VPS | 采用该代理的请求 |
| VPN / TUN + DNS 接管 | 设备查询进入客户端解析器，再将上游 DNS 请求经节点转发 | 被 VPN / TUN 接管的应用和流量 |

项目生成的 Linux `client.json` 没有本地 DNS 分流规则，默认只有 `proxy` 出站。应用以域名访问 HTTP / SOCKS 入口时，目标站点的解析发生在 VPS 一侧；这不等于接管了 Linux 系统解析器。`dig`、`nslookup` 或应用自行发起的 DNS 不会因设置 `HTTPS_PROXY` 自动进入代理。curl 的 `socks5://` 会在本机解析，应改用 `socks5h://`。[curl 参数依据](https://curl.se/docs/manpage.html#--socks5-hostname)

客户端需要自行解析时，推荐使用 **DoH，并明确让 DoH 连接经过代理节点**。本说明以 `https://1.1.1.1/dns-query` 为例：这是公共 DNS 服务地址，不是 VPS 地址。只填写 `1.1.1.1`，或只启用 DoH 加密，都不能证明请求经过 VPS。[DoH 说明](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/)

节点地址优先填写 `YOUR_SERVER_IP`，DoH 示例也使用 IP 地址，从而减少建立代理前的 DNS 依赖。如果节点地址填写域名，必须先通过可达的引导 DNS 或静态映射找到 VPS，不能让这一步依赖尚未建立的代理。REALITY 的 SNI 仍填写服务端配置的目标域名。

#### Windows、macOS、Linux 桌面：v2rayN

以下选项按 **v2rayN 7.24.9** 的界面资源和配置生成代码核对；其他版本名称可能不同。GUI 自带内核的版本与本仓库固定的 Linux 安装器版本是两回事。

1. 选择本项目节点，先使用**全局代理路由**验证。这里指内核的路由模式，仅启用“自动配置系统代理”不会接管所有应用的 DNS。
2. 进入“设置 → DNS 设置”的基础设置，将**远程 DNS**设为 `https://1.1.1.1/dns-query`。使用普通 `https://`；Xray 的 `https+local://` 会绕过内核路由直接连接，不适合此目的。
3. 若要求设备的普通 DNS 查询也经过代理，启用 **TUN**，按应用提示授予权限，并保留客户端生成的 DNS 接管规则；若有自动路由、严格路由选项，一并开启。只使用 HTTP/SOCKS 的程序可以不启用 TUN。
4. 严格验证时，不启用“绕过中国大陆”的 DNS / 域名分流，也不把测试应用排除在 TUN 外。**直连 DNS**和 **Bootstrap DNS**有各自用途：把“直连 DNS”也填成国外地址，仍然是直连。节点和 DoH 都使用 IP 时，测试链路不需要解析这两个入口的域名。
5. 保存并重启客户端连接，按下文核对实际路径。若启用了“自定义 DNS”或完整配置模板，基础设置可能不生效，应检查正在生效的配置，不能只修改一个被覆盖的页面。

根据该版本的配置生成逻辑，使用基础 DNS 设置和全局代理路由时，远程 DNS 交给代理出站；命中直连域名规则的 DNS 则可能交给直连出站。TUN 涉及的 sing-box DNS 配置有独立格式，不要把 Xray JSON 直接粘贴到 sing-box 页面。[Xray 配置生成依据](https://github.com/2dust/v2rayN/blob/7.24.9/v2rayN/ServiceLib/Services/CoreConfig/V2ray/V2rayDnsService.cs)、[sing-box 配置生成依据](https://github.com/2dust/v2rayN/blob/7.24.9/v2rayN/ServiceLib/Services/CoreConfig/Singbox/SingboxDnsService.cs)、[配置覆盖顺序](https://github.com/2dust/v2rayN/wiki/Faq#目前配置文件的生成流程)

这套设置的目标是让被 TUN 接管的公网 DNS 经节点转发。局域网发现、系统例外、其他 VPN、应用独立 DoH 等仍需按实际网络验证，不能仅凭 TUN 开关亮起就判断没有旁路。

#### Android：v2rayNG

以下选项按 **v2rayNG 2.2.6** 的设置和配置生成代码核对：

| 设置 | 建议值 / 操作 |
| --- | --- |
| 运行模式 | VPN；允许系统 VPN 请求，确保待测应用被纳入代理 |
| 启用本地 DNS | **开启**，表示将 DNS 查询导入客户端内核处理 |
| 远程 DNS | `https://1.1.1.1/dns-query` |
| VPN DNS | `1.1.1.1`，此栏只接受 IP，不能填 DoH URL |
| 路由 | 先用全局代理；验证时关闭绕过大陆及待测域名的直连规则 |
| 启用虚拟 DNS / FakeDNS | 初次验证可关闭；不是 DNS 走代理的必要条件 |

VPN DNS 是向 Android 提供的 DNS 地址；开启“本地 DNS”后，进入 VPN 的普通 53 端口查询由内核 DNS 模块接管，上游使用“远程 DNS”。“境内 DNS”用于直连规则，如果保留国内分流，相应解析也可能直连；不能把这种分流配置称为全部 DNS 经过代理。留空字段也可能采用默认 DNS，不能用“清空境内 DNS”代替路由检查。[设置项](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/res/xml/pref_settings.xml)、[DNS 路由实现](https://github.com/2dust/v2rayNG/blob/2.2.6/V2rayNG/app/src/main/java/com/v2ray/ang/core/CoreConfigManager.kt)

验证时可先关闭 Android 的“私人 DNS”和浏览器自身的“安全 DNS”，让测试只使用客户端提供的解析路径。若要保留这些独立解析器，需确认它们的 DoT / DoH 连接也经过 VPN 和代理路由；53 端口接管不能单独控制它们。修改后重新连接 VPN。

<a id="ios-dns"></a>

#### iOS / iPadOS：Shadowrocket（小火箭）

以 **2.2.92** 为参考。小火箭支持 DNS over Proxy；它与仅设置公共 DNS、仅启用 DoH 是不同的设置。[应用官方功能说明](https://apps.apple.com/us/app/shadowrocket/id932747118)

1. 在“配置”中确认当前正在使用的配置文件，先备份或复制一份，然后打开其编辑入口（通常为 `ⓘ → 通用 → DNS 覆写`）。不要只修改节点的 SNI；SNI 不是 DNS 服务器。
2. DNS 覆写使用 `https://1.1.1.1/dns-query#proxy`；这里的 `#proxy` 指示 DNS 请求经过代理。备用 DNS 也使用带 `#proxy` 的地址，例如 `https://1.0.0.1/dns-query#proxy`，不要保留 `system` 或将备用项留空后假定已关闭回退。
3. 关闭“直连域名使用系统 DNS”一类选项。如果已有独立直连 DNS、模块或其他 DNS 覆写，检查它们是否覆盖当前设置，移除测试域名的系统 / 直连解析路径。
4. 保存并选用这份配置，选中本项目节点，先将全局路由设为“代理”，重新连接 VPN。开启日志，核对 DoH 请求使用所选节点；“配置”路由模式下还需要检查规则和最终策略。

在配置文件中合并到已有的 `[General]` 段，不要创建重复段或重复键：

```ini
[General]
dns-server = https://1.1.1.1/dns-query#proxy
fallback-dns-server = https://1.0.0.1/dns-query#proxy
dns-direct-system = false
```

这只控制小火箭解析器使用的 DNS；应用自带的 DoH / DoT 仍需通过代理路由。节点本身使用 VPS IP，可避免为建立 DNS over Proxy 再去解析节点域名。这里未在 iPhone 上实测，界面和配置键应结合 2.2.92 的应用内说明核对，并完成下文的实际验证。

#### Linux 命令行：按应用使用远程解析

先按 [Linux 客户端说明](#xray-linux) 启动 Xray。以下两种方式都会将目标域名交给本项目代理，且不修改系统 DNS：

```bash
# HTTP CONNECT 传递目标域名
curl --noproxy '' --proxy http://127.0.0.1:1187 \
  --connect-timeout 10 --max-time 30 -I https://example.com

# 注意 socks5h 末尾的 h
curl --noproxy '' --proxy socks5h://127.0.0.1:1180 \
  --connect-timeout 10 --max-time 30 -I https://example.com
```

Codex 使用 [进程代理命令](#xray-codex) 即可，避免 `NO_PROXY` 包含待测目标。上述结论适用于采用 HTTP 代理连接的网站请求，不涵盖 Codex 子进程自行调用 `dig` 等程序。

若只是想手工查询 DNS，也可把这一个 DoH 请求发给代理：

```bash
curl --fail --silent --show-error --noproxy '' \
  --proxy http://127.0.0.1:1187 \
  --connect-timeout 10 --max-time 30 \
  --header 'accept: application/dns-json' \
  'https://1.1.1.1/dns-query?name=example.com&type=A'
```

预期 JSON 中 `Status` 为 `0`，并有 `Answer`。这个命令只验证此请求，不会改变其他程序的 DNS。[Cloudflare JSON 查询接口](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/)

若需要 Linux 整机 DNS 接管，可使用上面的 v2rayN TUN 方式；本项目原生命令行客户端没有自动安装 TUN、DNS 监听器或系统路由。不要把 `/etc/resolv.conf` 改成 `127.0.0.1` 来指向 HTTP 1187 / SOCKS 1180：这两个端口不提供普通 DNS 服务。

#### 验证与常见误判

1. **先确认网站出口**：浏览器或代理 curl 访问 `https://www.cloudflare.com/cdn-cgi/trace`，检查 `ip=` 为 VPS 出口。出口正确仍不能单独证明 DNS 没有直连。
2. **确认 DNS 连接路由**：开启客户端的 DNS / 连接日志，用未缓存的测试域名触发查询，核对访问 DoH 上游的连接走代理节点；改回日常分流规则后再测一次。临时日志用后关闭，发布日志前隐藏地址、节点参数和访问域名。
3. **核对物理网络出口**：有条件时在实际网卡抓包，检查待测域名是否经本地路由器 / 运营商 DNS 发出。TUN 内或回环接口上出现 DNS 是正常现象，应检查物理出口。抓不到 53 端口流量也不足以证明没有泄漏，因为 DoH / DoT 可能直连。
4. **检查旁路解析器**：浏览器“安全 DNS”、Android“私人 DNS”、iOS 的其他 DNS 描述文件 / 隐私中继、IPv6、应用分流和其他 VPN 都可能影响测试路径。只关闭 AAAA 查询不能代替接管 IPv6 网络流量。
5. **正确理解 DNS 检测页**：检测通常显示递归解析器的出口 IP，它不必等于 VPS IP；公共 DNS 的 Anycast 地理位置也不是可靠的判据。浏览器测试只能覆盖本次浏览器样本，要结合客户端日志与物理网卡路径判断。

Linux 可在另一终端使用以下只读抓包命令，将 `YOUR_UPLINK_IFACE` 换成实际物理出口网卡；按 Ctrl+C 停止：

```bash
sudo tcpdump -ni YOUR_UPLINK_IFACE \
  '(udp port 53 or tcp port 53 or tcp port 853 or udp port 853)'
```

此过滤器不包含 443 上的 DoH；还应核对到 DoH 服务器 443 端口的连接是否直接从物理网卡发出。仅抓包观察，不需要修改防火墙或停止已有代理。

最后还要区分客户端与服务端：域名随代理连接传到 VPS 后，本项目服务端默认使用 VPS 自身的解析路径，并不保证使用客户端所填的 Cloudflare DoH。客户端 DNS 不经本地网络直出，与 VPS 到上游 DNS 是否加密是两个要求。本文只说明客户端设置，不改变服务器解析器。[Xray DNS 的路由与本地模式](https://xtls.github.io/config/dns.html)

<a id="xray-validation"></a>

### 验证摘要与适用范围

以下为 **2026-09-30** 的验证记录，不代表长期线路质量或所有平台均已实测：

- Linux amd64 的 Xray 26.3.27 镜像及原生客户端配置检查、固定摘要校验、HTTP / SOCKS5h 实际代理访问通过，出口确认为测试 VPS。重复初始化被拒绝，重复 `up` 复用容器；端口占用、目标不匹配、其他目录的同名项目及凭据隔离检查通过。
- Linux 上使用 Codex CLI **0.156.0**，经临时 HTTP 1187 → VPS TCP 8443 → OpenAI 完成真实请求，返回 `PROXY_OK`，约 **19.1 秒**；连接日志确认请求进入新代理。测试后客户端、服务端临时资源及凭据已清理，本机持久配置和旧服务保持原样。日常使用见[Codex 进程代理配置](#xray-codex)。
- 依赖安装器 **15 项隔离测试通过**；7 个系统版本 × 2 种架构的 **56 个固定 Docker 包版本**均在官方仓库中找到。Ubuntu 20.04 / Debian 13 amd64 容器的基础依赖实际安装及固定 Docker 包的 APT 模拟安装通过；未在容器中启动 Docker daemon。
- Debian 13 amd64 VPS 上重复运行安装器、`--check`、`--dry-run` 均通过，已有 Docker 29.6.2 / Compose 5.3.1 被复用；临时 Compose 2.35.1 的摘要校验及 Docker API 访问也通过。其他系统与 arm64 仅核对安装分支、软件包和摘要，尚未逐一完成全新 VPS 安装。
- iPhone / Shadowrocket 和各平台 DNS 防泄漏未全部实机验证；DNS 设置依据所列版本的官方配置逻辑核对，仍需结合设备日志和实际流量验证。目标网站的 TLS 检查也不能替代 REALITY 实际访问测试。

依赖安装器的隔离测试可在项目根目录执行，不安装软件、不调用真实 Docker：

```bash
python3 -m unittest discover -s xray/tests -v
```

下面保留原有 V2Ray 使用说明；其中的 VMess 参数、WebSocket 路径和旧客户端版本仅适用于原方案。

---

## 原有 V2Ray：WebSocket + TLS

用 Docker 一键部署基于 WebSocket + TLS 的 V2Ray。

## 1 获取域名及 VPS

- VPS：推荐 [Vultr](https://www.vultr.com/)、[EVOXT](https://console.evoxt.com/)

- 域名注册：freenom 可以免费注册，但国内好像比较麻烦，推荐 [Godaddy](https://www.godaddy.com/)、阿里云

然后在域名设置中，添加一条 A 记录，值为 VPS 的 IP 地址

## 2 服务端配置

以 root 用户运行运行如下脚本，`run.sh` 的参数依次为域名、邮箱、端口、websocket 路径、用户 ID，未填入的字段将随机生成；过程中 Let's Encrypt 验证时输入邮箱并输入 Yes

```sh
sudo apt install -y git
git clone https://github.com/Hongqin-Li/docker-v2ray.git
cd docker-v2ray
bash run.sh example.com example@gmail.com 443 /v2ray
```

查看生成的配置信息，对应于下文带 $ 的字段

```sh
cat config.txt
```

如果想要修改配置，则重新执行 `run.sh`，并在遇到替换证书时直接退出即可，然后重启 docker 服务

```sh
docker compose down
bash run.sh example2.com example2@gmail.com 4016 /v2ray2 44911282-01cc-4188-a0ba-21db91e9c864
docker compose up -d
```

## 3 客户端配置

无论是哪个平台，均需要配置如下几项

- 采用 VMESS 协议
- 填入服务器 IP 地址、域名 `$DOMAIN`、端口 `$PORT`、用户 ID `$UUID`、额外 ID（64）、等级（1）、网络类型（ws）、websocket 路径 `$WSPATH`
- 勾选 tls

Android 使用 [v2rayNG](https://github.com/2dust/v2rayNG)，到 release 中下载对应版本，我用的是 [v2rayNG_1.4.13_arm64-v8a.apk](https://github.com/2dust/v2rayNG/releases/download/1.4.13/v2rayNG_1.4.13_arm64-v8a.apk)，然后正常配置即可

Linux 图形管理可使用 [v2rayA](https://github.com/v2rayA/v2rayA)，按 [wiki](https://github.com/v2rayA/v2rayA/wiki/Usage) 安装后到 http://localhost:2017 中进行配置；纯命令行部署见下文。

Windows 使用 [V2RayW](https://github.com/Cenmrev/V2RayW)

1. 配置中填入端口、地址、用户 ID、额外 ID、等级、加密方式（auto）、网络类型（ws）
2. 传输设置的 Websocket 一栏：路径填 `$WSPATH`
3. 传输设置的 TLS 一栏：勾选“传输层加密 TLS”，其他都不勾，服务器域名填入你的域名，应用层协议协商 ALPN 填默认的 `http/1.1`

MacOS（x86） 使用 [V2RayX](https://github.com/Cenmrev/V2RayX)

1. 配置中填入地址、端口、用户 ID、额外 ID、等级、加密方式（auto）、网络类型（ws）
2. transport settings 的 WebSocket 一栏： path 填 `$WSPATH`，headers 填 `{"Host" : "$DOMAIN" }`
3. transport settings 的 TLS 一栏：勾选 Use TLS，其他都不勾，TLS serverName 填入你的域名，alpn 填 `http/1.1`

### Linux 命令行方式

本机采用解压二进制后直接运行的方式，目录为 `~/v2ray`，使用 **V2Ray 4.22.1** 和 `config2.json`；提供 SOCKS5 `1080`、HTTP `1087` 两个代理端口，通过 VMess + WebSocket + TLS 连接服务器。以下命令在 Linux **客户端机器**上执行。

**1. 准备程序**

下面以 Linux x86_64 为例，下载与本机部署相同版本的安装包；其他架构从 [v4.22.1 发布页](https://github.com/v2ray/v2ray-core/releases/tag/v4.22.1) 选择对应文件。需要预先安装 `curl` 和 `unzip`。

```bash
mkdir -p "$HOME/v2ray"
cd "$HOME/v2ray"
curl -fL --retry 3 -o v2ray-linux-64.zip \
  https://github.com/v2ray/v2ray-core/releases/download/v4.22.1/v2ray-linux-64.zip
unzip -n v2ray-linux-64.zip
chmod u+x v2ray v2ctl
./v2ray -version
```

已有程序和配置时，可以直接进入第 3 步检查配置。保留压缩包中的 `v2ctl`、`geoip.dat`、`geosite.dat`，与 `v2ray` 放在同一目录。

本文命令对应 V2Ray 4.x 的 `-config` / `-test` 参数。当前服务端与本机客户端均使用 4.22.1、`alterId: 64`，升级版本时需要一起核对两端配置；不要直接将下文命令套用到不同版本的客户端。

**2. 编写客户端配置**

在 `~/v2ray/config2.json` 中写入下面的配置，并按服务端 `~/docker-v2ray/config.txt` 替换：

| 客户端字段 | 服务端对应值 |
| --- | --- |
| `address`、`tlsSettings.serverName`、WebSocket `Host` 中的 `YOUR_DOMAIN` | `$DOMAIN`，与 TLS 证书匹配的域名 |
| `vnext` 中的 `port: 443` | `$PORT`，服务器对外暴露的 TLS 端口 |
| `id` 中的 `YOUR_UUID` | `$UUID` |
| `wsSettings.path` 中的 `/v2ray` | `$WSPATH` |
| `alterId: 64`、`level: 1` | 与服务端 VMess 用户配置一致 |

`1080`、`1087` 是客户端本地端口，服务端容器内部的 `30909` 不填在客户端的 `vnext.port` 中。示例供本机程序使用，监听 `127.0.0.1`，并使用服务端域名校验 TLS 证书。

```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "listen": "127.0.0.1",
      "port": 1080,
      "protocol": "socks",
      "settings": { "auth": "noauth", "udp": true }
    },
    {
      "listen": "127.0.0.1",
      "port": 1087,
      "protocol": "http",
      "settings": {}
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vmess",
      "settings": {
        "vnext": [
          {
            "address": "YOUR_DOMAIN",
            "port": 443,
            "users": [
              {
                "id": "YOUR_UUID",
                "level": 1,
                "alterId": 64,
                "security": "none"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
          "serverName": "YOUR_DOMAIN",
          "allowInsecure": false
        },
        "wsSettings": {
          "path": "/v2ray",
          "headers": { "Host": "YOUR_DOMAIN" }
        }
      }
    },
    { "protocol": "freedom", "tag": "direct" }
  ],
  "routing": {
    "domainStrategy": "IPOnDemand",
    "rules": [
      {
        "type": "field",
        "ip": ["geoip:private"],
        "outboundTag": "direct"
      }
    ]
  }
}
```

**3. 检查配置并启动**

先替换配置中的占位符，再执行检查。看到 `Configuration OK.` 表示配置有效，不代表已连通服务器。[V2Ray 命令行参数说明](https://www.v2fly.org/guide/command.html)

```bash
cd "$HOME/v2ray"
chmod 600 config2.json
./v2ray -test -config config2.json

# 前台运行，按 Ctrl-C 停止
./v2ray -config config2.json
```

需要退出终端后继续运行时，先停止前台进程，再使用后台方式；同一组端口只启动一个进程。

```bash
cd "$HOME/v2ray"
nohup ./v2ray -config config2.json >>v2ray.log 2>&1 &
printf '%s\n' "$!" >v2ray.pid

# 检查进程、监听端口和日志
ps -p "$(cat v2ray.pid)" -o pid,args
ss -lntp | grep -E ':(1080|1087)[[:space:]]'
tail -n 50 v2ray.log
```

这里将输出写入 `~/v2ray/v2ray.log`。修改 `config2.json` 后需要停止旧进程，再按上面的命令启动。后台进程停止方式如下，先确认显示的 PID 和命令属于该 V2Ray 实例：

```bash
cd "$HOME/v2ray"
ps -p "$(cat v2ray.pid)" -o pid,args
kill "$(cat v2ray.pid)"
rm -f v2ray.pid
```

**4. 使用代理**

SOCKS5 代理使用 `socks5h://`，将目标域名交给代理处理，避免 curl 先在本机解析目标网站。HTTP 代理使用 `http://127.0.0.1:1087`，即使目标网站是 HTTPS，代理地址仍以 `http://` 开头。

```bash
# SOCKS5 端口
curl --noproxy '' --proxy socks5h://127.0.0.1:1080 \
  --connect-timeout 10 --max-time 30 -I https://www.google.com

# HTTP 端口
curl --noproxy '' --proxy http://127.0.0.1:1087 \
  --connect-timeout 10 --max-time 30 -I https://www.google.com

# 与本机使用方式一致：仅为本次 Codex CLI 启动指定代理
HTTPS_PROXY=http://127.0.0.1:1087 codex
```

也可以让当前终端中支持代理环境变量的程序使用 HTTP 代理：

```bash
export HTTP_PROXY=http://127.0.0.1:1087
export HTTPS_PROXY=http://127.0.0.1:1087
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export NO_PROXY="${NO_PROXY:-${no_proxy:-localhost,127.0.0.1,::1}}"
export no_proxy="$NO_PROXY"
```

内网服务的域名后缀应加入 `NO_PROXY`，用逗号分隔，并同步 `no_proxy`；以上命令保留已有的排除列表。只需要某个程序走代理时，使用命令前缀即可，无需写入 shell 启动文件。

如果提示 `Connection refused`，先检查本地进程和端口；如果配置检查成功但访问失败，检查 `v2ray.log`，并核对服务器域名、TLS 端口、UUID 和 WebSocket 路径。

现在你可以开始使用了。

## 4 问题诊断

```sh
# 检查dns解析
nslookup $DOMAIN

# 检查服务端ip是否连得上
ping $IP

# 检查服务端默认的v2ray服务端口是否连得上
telnet $IP $PORT

# 检查本地客户端代理；1080 对应上面的 config2.json，其他客户端按实际端口调整
curl --proxy "socks5h://127.0.0.1:1080" --connect-timeout 10 --max-time 30 https://www.google.com
```

1. 服务端 ip 连接得上，但v2ray服务端口连不上：可能端口被封了，服务端更改 run.sh 中的 PORT 并重新配置，客户端配置换成新端口


## 参考资料

细节参考： <a href="https://www.4spaces.org/docker-compose-install-v2ray-ws-tls/" target="_blank" rel="noopener noreferrer">在docker-compose环境下以ws+tls方式搭建v2ray(So easy)</a>

相关配置参考： <a href="https://www.4spaces.org/v2ray-nginx-tls-websocket/" target="_blank" rel="noopener noreferrer">centos7基于nginx搭建v2ray服务端配置vmess+tls+websocket完全手册</a>

交流Telegram群组：[三好学生](https://t.me/goodgoodgoodstudent);
