set -o errexit

echo "NOTE: This script only tested on Debian 10"

DOMAIN=$1
EMAIL=$2

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

# Install docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker

# Install docker compose
curl -L "https://github.com/docker/compose/releases/download/1.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -f -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Modify domain and email
perl -i -pe "s/YOUR_DOMAIN/$DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
perl -i -pe "s/YOUR_DOMAIN/$DOMAIN/g" ./init-letsencrypt.sh
perl -i -pe "s/YOUR_EMAIL/$EMAIL/g" ./init-letsencrypt.sh

# Modify uuid
UUID=$(cat /proc/sys/kernel/random/uuid)
perl -i -pe "s/\"id\": \"[^\"]*\"/\"id\": \"$UUID\"/g" ./data/v2ray/config.json

bash init-letsencrypt.sh

echo $UUID > id.txt
echo "Generate UUID '$UUID' in id.txt"

