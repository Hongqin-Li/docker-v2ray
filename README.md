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

Linux 使用 [v2rayA](https://github.com/v2rayA/v2rayA)，按 [wiki](https://github.com/v2rayA/v2rayA/wiki/Usage) 安装后到 http://localhost:2017 中进行配置即可

Windows 使用 [V2RayW](https://github.com/Cenmrev/V2RayW)

1. 配置中填入端口、地址、用户 ID、额外 ID、等级、加密方式（auto）、网络类型（ws）
2. 传输设置的 Websocket 一栏：路径填 `$WSPATH`
3. 传输设置的 TLS 一栏：勾选“传输层加密 TLS”，其他都不勾，服务器域名填入你的域名，应用层协议协商 ALPN 填默认的 `http/1.1`

MacOS（x86） 使用 [V2RayX](https://github.com/Cenmrev/V2RayX)

1. 配置中填入地址、端口、用户 ID、额外 ID、等级、加密方式（auto）、网络类型（ws）
2. transport settings 的 WebSocket 一栏： path 填 `$WSPATH`，headers 填 `{"Host" : "$DOMAIN" }`
3. transport settings 的 TLS 一栏：勾选 Use TLS，其他都不勾，TLS serverName 填入你的域名，alpn 填 `http/1.1`

现在你可以开始使用了。

## 4 问题诊断

```sh
# 检查dns解析
nslookup $DOMAIN

# 检查服务端ip是否连得上
ping $IP

# 检查服务端默认的v2ray服务端口是否连得上
telnet $IP $PORT

# 检查本地客户端的代理是否有效，10808是config.json里面inbounds的端口
curl --proxy curl --proxy "socks://127.0.0.1:10808" https://www.google.com
```

1. 服务端 ip 连接得上，但v2ray服务端口连不上：可能端口被封了，服务端更改 run.sh 中的 PORT 并重新配置，客户端配置换成新端口


## 参考资料

细节参考： <a href="https://www.4spaces.org/docker-compose-install-v2ray-ws-tls/" target="_blank" rel="noopener noreferrer">在docker-compose环境下以ws+tls方式搭建v2ray(So easy)</a>

相关配置参考： <a href="https://www.4spaces.org/v2ray-nginx-tls-websocket/" target="_blank" rel="noopener noreferrer">centos7基于nginx搭建v2ray服务端配置vmess+tls+websocket完全手册</a>

交流Telegram群组：[三好学生](https://t.me/goodgoodgoodstudent);
