#!/bin/sh
set -eu

FILE="/gluetun/forwarded_port"

# czekaj aż pojawi się poprawny numer portu (max ~3 min)
i=0
while [ $i -lt 90 ]; do
  if [ -s "$FILE" ] && grep -Eq '^[0-9]+$' "$FILE"; then
    PORT="$(tr -dc '0-9' < "$FILE")"
    break
  fi
  i=$((i+1))
  sleep 2
done

if [ -z "${PORT:-}" ]; then
  echo "[cont-init.d] WARN: forwarded_port nie znaleziony – RT_INC_PORT bez zmian"
  exit 0
fi

# ustaw zmienną środowiskową dla wszystkich usług w kontenerze (s6)
mkdir -p /var/run/s6/container_environment
printf "%s" "$PORT" > /var/run/s6/container_environment/RT_INC_PORT
printf "%s" "$PORT" > /var/run/s6/container_environment/RT_DHT_PORT

echo "[cont-init.d] INFO: RT_INC_PORT=$PORT ustawione"
echo "[cont-init.d] INFO: RT_DHT_PORT=$PORT ustawione"
