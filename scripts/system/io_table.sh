#!/usr/bin/env bash
# Usage: io_table.sh [interval_seconds]
# Domyślnie: 1s. Działa do Ctrl+C. IO: B/s, KiB/s, MiB/s...  Usage: used/total TB.

set -euo pipefail
INTERVAL="${1:-1}"

command -v df >/dev/null || { echo "Brak df"; exit 1; }
command -v lsblk >/dev/null || { echo "Brak lsblk"; exit 1; }

# Formatowanie bajtów/s do B/s, KiB/s, MiB/s, GiB/s, TiB/s
human_bps() {
  awk -v bps="$1" 'BEGIN{
    u[0]="B/s"; u[1]="KiB/s"; u[2]="MiB/s"; u[3]="GiB/s"; u[4]="TiB/s";
    val=bps+0; i=0;
    while (val>=1024 && i<4) { val/=1024.0; i++ }
    if (i==0) { printf("%.0f %s", val, u[i]); }
    else { printf("%.1f %s", val, u[i]); }
  }'
}

# Konwersja bajtów na TB (10^12), z 1 miejscem po przecinku
to_TB() { awk -v b="$1" 'BEGIN{ printf("%.1f", b/1000000000000) }'; }

# 1) Pobierz z df tylko realne FS i ich rozmiary w bajtach (bez -P!)
mapfile -t DF_ENTRIES < <(
  df -B1 --output=source,target,size,used,fstype | awk '
    NR>1 && $5 !~ /^(tmpfs|devtmpfs|overlay|squashfs|aufs|ramfs)$/ {print $1"\t"$2"\t"$3"\t"$4"\t"$5}'
)

declare -A MP_BY_KEY DISPLAY_BY_KEY PARENT_BY_KEY SECSIZE_BY_KEY USEDB_BY_KEY SIZEB_BY_KEY
TARGETS=()

for line in "${DF_ENTRIES[@]}"; do
  dev=$(awk -F'\t' '{print $1}' <<<"$line")
  mp=$(awk -F'\t' '{print $2}' <<<"$line")
  sizeb=$(awk -F'\t' '{print $3}' <<<"$line")
  usedb=$(awk -F'\t' '{print $4}' <<<"$line")

  [[ "$dev" =~ ^/dev/ ]] || continue

  # Nazwy zgodne z /proc/diskstats
  kname=$(lsblk -no KNAME "$dev" 2>/dev/null | head -n1)
  [[ -z "$kname" ]] && kname="$(basename "$dev")"
  pkname=$(lsblk -no PKNAME "$dev" 2>/dev/null | head -n1)
  [[ -z "$pkname" ]] && pkname="$kname"

  # Rozmiar sektora (preferuj logical_block_size)
  if [[ -r "/sys/block/${pkname}/queue/logical_block_size" ]]; then
    secsize=$(</sys/block/${pkname}/queue/logical_block_size)
  elif [[ -r "/sys/block/${pkname}/queue/hw_sector_size" ]]; then
    secsize=$(</sys/block/${pkname}/queue/hw_sector_size)
  else
    secsize=512
  fi

  TARGETS+=("$kname")
  MP_BY_KEY["$kname"]="$mp"
  DISPLAY_BY_KEY["$kname"]="$(basename "$dev")"
  PARENT_BY_KEY["$kname"]="$pkname"
  SECSIZE_BY_KEY["$kname"]="$secsize"
  USEDB_BY_KEY["$kname"]="$usedb"
  SIZEB_BY_KEY["$kname"]="$sizeb"
done

((${#TARGETS[@]})) || { echo "Brak pasujących urządzeń z df."; exit 1; }

print_header() {
  printf "%-16s %-40s %14s %14s %-16s\n" "device" "mountpoint" "IO read" "IO write" "usage"
  printf "%-16s %-40s %14s %14s %-16s\n" "----------------" "----------------------------------------" "--------------" "--------------" "----------------"
}

# Snapshoty /proc/diskstats
read_diskstats() {
  declare -gA RSEC WSEC
  RSEC=(); WSEC=()
  # /proc/diskstats: 3=name, 6=sectors_read, 10=sectors_written
  while read -r _ _ name _ _ r_sect _ _ _ w_sect _rest; do
    RSEC["$name"]="$r_sect"
    WSEC["$name"]="$w_sect"
  done < /proc/diskstats
}

clear
echo "Odświeżanie co ${INTERVAL}s — IO (df + /proc/diskstats)"
print_header
read_diskstats

while true; do
  declare -A PREV_R=() PREV_W=()
  for k in "${TARGETS[@]}"; do
    PREV_R["$k"]="${RSEC[$k]:-0}"
    PREV_W["$k"]="${WSEC[$k]:-0}"
  done

  sleep "$INTERVAL"
  read_diskstats

  clear
  echo "Odświeżanie co ${INTERVAL}s — IO (df + /proc/diskstats)"
  print_header

  for k in "${TARGETS[@]}"; do
    mp="${MP_BY_KEY[$k]}"
    disp="${DISPLAY_BY_KEY[$k]}"
    ss="${SECSIZE_BY_KEY[$k]}"

    r1=${PREV_R[$k]:-0}; r2=${RSEC[$k]:-0}
    w1=${PREV_W[$k]:-0}; w2=${WSEC[$k]:-0}
    dr=$(( r2>=r1 ? r2-r1 : 0 ))
    dw=$(( w2>=w1 ? w2-w1 : 0 ))

    # Bajty/s = delta_sektorów * rozmiar_sektora / INTERVAL
    read_bps=$(( dr * ss / INTERVAL ))
    write_bps=$(( dw * ss / INTERVAL ))

    usedb="${USEDB_BY_KEY[$k]:-0}"
    sizeb="${SIZEB_BY_KEY[$k]:-0}"
    usage="$(to_TB "$usedb")/$(to_TB "$sizeb") TB"

    printf "%-16s %-40s %14s %14s %-16s\n" \
      "$disp" "$mp" "$(human_bps "$read_bps")" "$(human_bps "$write_bps")" "$usage"
  done
done
