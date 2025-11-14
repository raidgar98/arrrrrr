#!/bin/bash

find . -type f -iname '*.mkv' -print0 \
  | while IFS= read -r -d '' f; do
      # rozdzielczość (np. 1920x1080)
      res=$(ffprobe -v error -select_streams v:0 \
                    -show_entries stream=width,height \
                    -of csv=p=0:s=x "$f")

      # długość w sekundach → HH:MM:SS
      dur=$(ffprobe -v error -show_entries format=duration \
                    -of default=noprint_wrappers=1:nokey=1 "$f")
      hms=$(echo "$dur" | awk '{h=int($1/3600); m=int(($1%3600)/60); s=int($1%60);
                               printf "%02d:%02d:%02d", h,m,s}')

      # rozmiar w formacie czytelnym (MiB/GiB)
      size=$(du -h "$f" | cut -f1)

      printf '%s | %s | %s | %s\n' "$f" "$res" "$hms" "$size"
    done
