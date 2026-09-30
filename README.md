# V2ray Quick Start

用 Docker 一键部署基于 WebSocket + TLS 的 v2ray

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
