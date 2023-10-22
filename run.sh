set -o errexit

echo "NOTE: This script only tested on Debian 10"

DOMAIN=$1
EMAIL=$2
PORT=443

if [ -z "$DOMAIN" ]; then
  echo -n "Please provide your domain: "
  read DOMAIN
fi

if [ -z "$EMAIL" ]; then
  echo -n "Please provide your email: "
  read EMAIL
fi

echo "Your domain is $DOMAIN"
echo "Your email is $EMAIL"

# Modify domain and email
sed -i -e "s/server_name [^ ]*; #YOUR_DOMAIN/server_name $DOMAIN; #YOUR_DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/[^/]*\/fullchain.pem; #YOUR_DOMAIN/$DOMAIN\/fullchain.pem; #YOUR_DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/[^/]*\/privkey.pem; #YOUR_DOMAIN/$DOMAIN\/privkey.pem; #YOUR_DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
sed -i -e "s/\"[^\"]*\" #YOUR_DOMAIN/\"$DOMAIN\" #YOUR_DOMAIN/g" ./init-letsencrypt.sh
sed -i -e "s/\"[^\"]*\" #YOUR_EMAIL/\"$EMAIL\" #YOUR_EMAIL/g" ./init-letsencrypt.sh
sed -i -e "s/\"[^:]*:443\" #YOUR_PORT/\"$PORT:443\" #YOUR_PORT/g" ./docker-compose.yml

# Modify uuid
UUID=$(cat /proc/sys/kernel/random/uuid)
perl -i -pe "s/\"id\": \"[^\"]*\"/\"id\": \"$UUID\"/g" ./data/v2ray/config.json

# Install docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker

# Install docker compose
curl -L "https://github.com/docker/compose/releases/download/1.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -f -s /usr/local/bin/docker-compose /usr/bin/docker-compose

bash init-letsencrypt.sh

echo $UUID > id.txt
echo "Generate UUID '$UUID' in id.txt"

