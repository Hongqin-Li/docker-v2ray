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
ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Install git and clone repo
sudo apt install -y git
git clone https://github.com/Hongqin-Li/docker-v2ray.git

# Modify domain and email
cd docker-v2ray
perl -i -pe "s/YOUR_DOMAIN/$DOMAIN/g" ./data/nginx/conf.d/v2ray.conf
perl -i -pe "s/YOUR_DOMAIN/$DOMAIN/g" ./init-letsencrypt.sh
perl -i -pe "s/YOUR_EMAIL/$EMAIL/g" ./init-letsencrypt.sh

bash init-letsencrypt.sh
cd ..

