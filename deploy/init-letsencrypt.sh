#!/bin/sh
# One-time Let's Encrypt bootstrap. Run on the EC2 box AFTER:
#   - the DNS A record kinomaniak.bnbg.pl -> Elastic IP resolves, and
#   - .env.prod exists in this directory.
set -e

domain="kinomaniak.bnbg.pl"
email="bartlomiej.gozlinski@gmail.com"   # LE expiry notices
rsa_key_size=4096
data_path="./certbot"
staging=0   # set to 1 to test against LE staging (avoids rate limits)

compose="docker compose -f docker-compose.prod.yml"

# This is a ONE-TIME bootstrap. Renewals happen automatically via the certbot
# service in docker-compose.prod.yml — never re-run this on a live box. Re-running
# is what mints duplicate `-0001` lineages and dummy-cert (`CN=localhost`) messes,
# and burns Let's Encrypt's "5 duplicate certs/week" limit. So: refuse if a cert
# already exists, and tell the operator how to deliberately re-issue.
if [ -d "$data_path/conf/live/$domain" ]; then
  echo "A certificate already exists at $data_path/conf/live/$domain."
  echo "This bootstrap is one-time only; renewals are automatic (certbot service)."
  echo "To intentionally re-issue, remove the existing lineage first, then re-run:"
  echo "  $compose run --rm --entrypoint 'certbot delete --cert-name $domain' certbot   # a real cert"
  echo "  # or a leftover dummy: sudo rm -rf $data_path/conf/live/$domain $data_path/conf/archive/$domain $data_path/conf/renewal/$domain.conf"
  echo "Aborting — no changes made."
  exit 1
fi

# 1. Recommended TLS params referenced by nginx (options-ssl-nginx.conf, dhparams).
if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
  echo "### Downloading recommended TLS parameters ..."
  mkdir -p "$data_path/conf"
  curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
    -o "$data_path/conf/options-ssl-nginx.conf"
  curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
    -o "$data_path/conf/ssl-dhparams.pem"
fi

# 2. Dummy self-signed cert so nginx can start its :443 block.
echo "### Creating dummy certificate ..."
live_path="/etc/letsencrypt/live/$domain"
mkdir -p "$data_path/conf/live/$domain"
$compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout '$live_path/privkey.pem' \
    -out '$live_path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

# 3. Start nginx against the dummy cert.
echo "### Starting nginx ..."
$compose up --force-recreate -d nginx

# 4. Drop the dummy and request the real certificate over the webroot challenge.
echo "### Deleting dummy certificate ..."
$compose run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/$domain && \
  rm -Rf /etc/letsencrypt/archive/$domain && \
  rm -Rf /etc/letsencrypt/renewal/$domain.conf" certbot

echo "### Requesting Let's Encrypt certificate ..."
staging_arg=""
if [ "$staging" != "0" ]; then staging_arg="--staging"; fi
$compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email $email \
    -d $domain \
    --rsa-key-size $rsa_key_size \
    --agree-tos --no-eff-email" certbot

# 5. Reload nginx with the real cert.
echo "### Reloading nginx ..."
$compose exec nginx nginx -s reload
echo "### Done. https://$domain should now serve a valid certificate."
