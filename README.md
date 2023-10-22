# V2ray Quick Start

用 Docker 一键部署基于 WebSocket + TLS 的 v2ray



## 1 获取域名及 VPS

- 域名注册：freenom 可以免费注册，但国内好像比较麻烦，推荐 [Godaddy](https://www.godaddy.com/)

- VPS：推荐 [Vultr]()，即可获得$100，推荐上新的 <a href="https://www.aliyunhost.net/vultr-korea-datacenter-launch/" target="_blank">Vultr韩国机房</a> 。

然后在域名设置中，添加一条 A 记录，值为 VPS 的 IP 地址


## 2 服务端配置

以下操作均以 root 用户进行

你可以使用如下的一键脚本，并按提示输入域名和邮箱，然后 Let's Encrypt 验证时输入邮箱并输入 Yes

```bash
sudo apt install -y git
git clone https://github.com/Hongqin-Li/docker-v2ray.git
cd docker-v2ray
bash run.sh
```

如果成功运行，则跳过这一节

### 2.1 安装 Docker

- 安装

```bash
$ curl -fsSL https://get.docker.com -o get-docker.sh
$ sh get-docker.sh
```

**注：** 这一步如果是CENTOS 8，可能会出现 `requires containerd.io >= 1.2.2-3错误` -> [解决办法](https://www.4spaces.org/docker-ce-install-containerd-io-error/)。

- 添加用户到用户组(需退出当前会话重启登录才生效)

```bash
$ gpasswd -a $USER docker
```

- 启动

```bash
$ systemctl start docker
```

- 设置 Docker 开机自启动

```bash
$ systemctl enable docker
```

- 安装 `docker-compose`

```bash
$ curl -L "https://github.com/docker/compose/releases/download/1.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
$ chmod +x /usr/local/bin/docker-compose
$ ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
```

### 2.2 安装 git 并 clone 代码

```bash
$ sudo apt install -y git
$ git clone https://github.com/Hongqin-Li/docker-v2ray.git
```

或者你可以下载后在上传到你的VPS。

### 2.3 修改 v2ray 配置

进入 `docker-v2ray` 目录开始修改配置。

1. 修改 `init-letsencrypt.sh` 中的 `domains` 和 `email` 为自己的域名和邮箱。
2. 修改 `data/v2ray/config.json` 中的 ID 为**随机 ID**，如 `"id": "bae399d4-13a4-46a3-b144-4af2c0004c2e"`。
3. 修改 `data/nginx/conf.d/v2ray.conf` 中所有`your_domain`为自己的域名。

### 2.4 部署v2ray

```bash
$ bash init-letsencrypt.sh
```



## 3 客户端配置

无论是哪个平台，均需要配置如下几项

- 采用 VMESS 协议
- 填入地址、端口（443）、用户 ID、额外 ID、等级、网络类型（ws），和 `data/v2ray/config.json` 中的值对应
- 勾选 tls

Android 使用 [v2rayNG](https://github.com/2dust/v2rayNG)，到 release 中下载对应版本，我用的是 [v2rayNG_1.4.13_arm64-v8a.apk](https://github.com/2dust/v2rayNG/releases/download/1.4.13/v2rayNG_1.4.13_arm64-v8a.apk)，然后正常配置即可

Linux 使用 [v2rayA](https://github.com/v2rayA/v2rayA)，按 [wiki](https://github.com/v2rayA/v2rayA/wiki/Usage) 安装后到 http://localhost:2017 中进行配置即可

Windows 使用 [V2RayW](https://github.com/Cenmrev/V2RayW)

1. 配置中填入端口（443）、地址、用户 ID、额外 ID、等级、加密方式（auto）、网络类型（ws）
2. 传输设置的 Websocket 一栏：路径填 `/v2ray`
3. 传输设置的 TLS 一栏：勾选“传输层加密 TLS”，其他都不勾，服务器域名填入你的域名，应用层协议协商 ALPN 填默认的 `http/1.1`



现在你可以开始使用了。

## 4 问题诊断

```sh
# 检查dns解析
nslookup $YOUR_DOMAIN

# 检查服务端ip是否连得上
ping $YOUR_IP

# 检查服务端默认的v2ray服务端口是否连得上
ping -p 443 $YOUR_IP

# 检查本地客户端的代理是否有效，10808是config.json里面inbounds的端口
curl --proxy curl --proxy "socks://127.0.0.1:10808" https://www.google.com
```

1. 服务端 ip 连接得上，但v2ray服务端口连不上：可能端口被封了，服务端更改 run.sh 中的 PORT 并重新配置，客户端配置换成新端口


## 参考资料

细节参考： <a href="https://www.4spaces.org/docker-compose-install-v2ray-ws-tls/" target="_blank" rel="noopener noreferrer">在docker-compose环境下以ws+tls方式搭建v2ray(So easy)</a>

相关配置参考： <a href="https://www.4spaces.org/v2ray-nginx-tls-websocket/" target="_blank" rel="noopener noreferrer">centos7基于nginx搭建v2ray服务端配置vmess+tls+websocket完全手册</a>

交流Telegram群组：[三好学生](https://t.me/goodgoodgoodstudent);
