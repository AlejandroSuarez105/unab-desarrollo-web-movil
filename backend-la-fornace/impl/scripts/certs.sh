#!/usr/bin/env bash
# Genera una CA del proyecto y un certificado por componente (solo para desarrollo y pruebas).
# Las llaves privadas quedan en $RUN_DIR/certs y NO se versionan.
set -euo pipefail
RUN_DIR="${RUN_DIR:-$(cd "$(dirname "$0")/.." && pwd)/.run}"
D="$RUN_DIR/certs"; mkdir -p "$D"; chmod 700 "$D"
COMPONENTES="api-gateway graphql-gateway auth-service clients-service inventory-service orders-service payments-service dispatch-service notifications-service pasarela-prueba correo-prueba"
if [ ! -f "$D/ca.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=Fornace CA (desarrollo)" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "subjectKeyIdentifier=hash" -keyout "$D/ca.key" -out "$D/ca.crt" 2>/dev/null
fi
for c in $COMPONENTES; do
  [ -f "$D/$c.crt" ] && continue
  openssl req -newkey rsa:2048 -nodes -subj "/CN=$c" -keyout "$D/$c.key" -out "$D/$c.csr" 2>/dev/null
  printf "subjectAltName=DNS:localhost,DNS:$c,IP:127.0.0.1\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth,clientAuth\nauthorityKeyIdentifier=keyid\nsubjectKeyIdentifier=hash\n" > "$D/$c.ext"
  openssl x509 -req -in "$D/$c.csr" -CA "$D/ca.crt" -CAkey "$D/ca.key" -CAcreateserial -days 365 \
    -extfile "$D/$c.ext" -out "$D/$c.crt" 2>/dev/null
  rm -f "$D/$c.csr" "$D/$c.ext"
done
chmod 600 "$D"/*.key
echo "certificados en $D"
