set -Eeuo pipefail

# --- konfiguracja opcjonalna ---
LOG_PATH="${RT_ATOMIC_LOG:-/media/logs}"   # zmień lub ustaw RT_ATOMIC_LOG w env
LOG_FILE="$LOG_PATH/core.log"
USER_SCRIPT="${RT_USER_SCRIPT:-/user-scripts/organise_by_filename.py}"     # Twój skrypt (label, dest, hash)
USER_STOP_SCRIPT="${RT_USER_SCRIPT:-/user-scripts/stop.py}"     # Twój skrypt (label, dest, hash)
# -------------------------------

daemonize() {
  # uruchom ciężką robotę w tle i natychmiast wróć (nie blokuj rTorrenta)
  # używamy setsid+nohup, żeby odczepić od TTY/rTorrenta
  exec setsid nohup bash -c "$1" > "$LOG_PATH/$2.log" 2>&1 < /dev/null &
}

main_job() {
  local SRC="$1" DESTDIR="$2" LABEL="${3:-}" HASH="${4:-}"

  if [[ "$LABEL" != "Filmy" && "$LABEL" != "Seriale" && "$LABEL" != "Anime" && "$LABEL" != "Filmografia" ]]; then
    exit 0
  fi


  BASENAME="$(basename -- "$SRC")"
  DEST="$DESTDIR/$BASENAME"

  echo "DEST = $DEST"
  echo "SRC= $SRC"
  echo "BASENAME= $BASENAME"

#   Pause torrent before copy
  python3 "$USER_STOP_SCRIPT" "$HASH" || true

  ionice -c2 -n0 rsync -aHAX --delete --inplace --remove-source-files --preallocate --fsync --bwlimit=20M --info=progress2 "$SRC" "$DEST"
#   ionice -c2 -n0 mv "$SRC" "$DEST"

  # 5) Twój skrypt użytkownika (jeśli istnieje)
  if [ -x "$USER_SCRIPT" ] || [ -f "$USER_SCRIPT" ]; then
    python3 "$USER_SCRIPT" "$LABEL" "$HASH" "$DEST" || true
  fi
}


# ^@sh /media/rt_atomic_copy.sh /downloads/temp/Lie.Down.with.Lions.1994.720p.PL.WEB-DL.AC3.H.264-PTTrG/ /downloads/complete/Filmy Filmy 3FE46C2B4918CC95E104FE28B306956E4D3DCF64
echo "STARTING...."
# --- wejście ---
SRC="${1:?brak SRC}"
DESTDIR="${2:?brak DESTDIR}"
LABEL="${3:-}"
HASH="${4:-}"

echo "ARGUMENTS PARSED...." | tee -a $LOG_FILE

# jeśli nie jesteśmy jeszcze w tle – odpal właściwą robotę asynchronicznie i od razu wyjdź
if [ -z "${RT_DAEMONIZED:-}" ]; then
  echo "STARTING DAEMON...." | tee -a $LOG_FILE
  CMD="RT_DAEMONIZED=1 sh \"$0\" \"${SRC}\" \"${DESTDIR}\" \"${LABEL}\" \"${HASH}\""
  daemonize "$CMD" $HASH
  echo "DAEMON STARTED...." | tee -a $LOG_FILE
  exit 0
fi

echo "ENTERING MAIN FUNCTION...." | tee -a $LOG_FILE
# tu już pracuje proces w tle
main_job "$SRC" "$DESTDIR" "$LABEL" "$HASH"



# rsync -aHAX --delete --inplace --remove-source-files --preallocate --fsync --info=progress2 "$SRC" "$DEST"
