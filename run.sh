#!/bin/bash
set -o errexit

DOMAIN=$1
EMAIL=$2
PORT=$3
WSPATH=$4
UUID=$5

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "usage: bash run.sh domain email [port [wspath [uuid]]]"
  exit 1
fi

if [ -z "$PORT" ]; then
  PORT=$(shuf -i 20000-65000 -n 1)
fi

if [ -z "$WSPATH" ]; then
  WSPATH="/$(shuf -er -n20  {A..Z} {a..z} {0..9} | tr -d '\n')"
fi

if [ -z "$UUID" ]; then
  UUID=$(cat /proc/sys/kernel/random/uuid)
fi

echo "Your domain is $DOMAIN" > config.txt
echo "Your email is $EMAIL" >> config.txt
echo "Your port is $PORT" >> config.txt
echo "Your wspath is $WSPATH" >> config.txt
echo "Your uuid is $UUID" >> config.txt

# Modify config
sed -i -e "s/server_name [^ ]*; #YOUR_DOMAIN/server_name $DOMAIN; #YOUR_DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/[^/]*\/fullchain.pem; #YOUR_DOMAIN/$DOMAIN\/fullchain.pem; #YOUR_DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/[^/]*\/privkey.pem; #YOUR_DOMAIN/$DOMAIN\/privkey.pem; #YOUR_DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/\"[^\"]*\" #YOUR_DOMAIN/\"$DOMAIN\" #YOUR_DOMAIN/g" ./init-letsencrypt.sh
sed -i -e "s/\"[^\"]*\" #YOUR_EMAIL/\"$EMAIL\" #YOUR_EMAIL/g" ./init-letsencrypt.sh
sed -i -e "s/\"[^:]*:443\" #YOUR_PORT/\"$PORT:443\" #YOUR_PORT/g" ./docker-compose.yml
sed -i -e "s%location [^ ]* { #YOUR_WSPATH%location $WSPATH { #YOUR_WSPATH%g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/\"id\": \"[^\"]*\"/\"id\": \"$UUID\"/g" ./data/v2ray/config.json
sed -i -e "s%path\": \"[^\"]*\"%path\": \"$WSPATH\"%g" ./data/v2ray/config.json

# Install docker if not exists
if ! [ -x "$(command -v docker)" ]; then
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  systemctl start docker
  systemctl enable docker
fi

# Install docker-compose if not exists
if ! [ -x "$(command -v docker-compose)" ]; then
  curl -L "https://github.com/docker/compose/releases/download/1.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
  ln -f -s /usr/local/bin/docker-compose /usr/bin/docker-compose
fi

bash init-letsencrypt.sh
