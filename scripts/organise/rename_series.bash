#!/bin/bash

series_name=$1

for f in *.mkv ; do sep=$(echo "$f" | sed -E "s|.*(S[0-9]+E[0-9]+)\.mkv|${series_name} \1.mkv|g"); mv "${f}" "${sep}"; done
