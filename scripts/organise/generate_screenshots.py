#!/usr/bin/env python3
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests


# === KONFIGURACJA ===
IMGPUSH_BASE_URL = "https://images.papug.it"  # bez trailing slash
NUM_SHOTS = 4

# rozmiar miniaturki (forum thumb):
THUMB_WIDTH = None #400   # ustaw na None, jeśli chcesz pełny rozmiar
THUMB_HEIGHT = None #0    # 0 = ignoruj wysokość (skaluj proporcjonalnie)


def run(cmd):
    """Uruchom proces i zwróć stdout jako tekst, rzucając wyjątek przy błędzie."""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def get_duration_seconds(path):
    """Pobierz długość wideo w sekundach przy pomocy ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    out = run(cmd)
    try:
        return float(out)
    except ValueError:
        raise RuntimeError(f"Nie udało się sparsować długości z ffprobe: {out!r}")


def format_timestamp(seconds):
    """Zamień float sekund na format HH:MM:SS.mmm z tolerancją ffmpeg."""
    ms = int(round(seconds * 1000))
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def make_screens(video_path, out_dir, num=NUM_SHOTS):
    """Wygeneruj num screenshotów i zwróć listę ścieżek."""
    duration = get_duration_seconds(video_path)
    if duration <= 0:
        raise RuntimeError("Wideo ma nielogiczną długość (<= 0 s).")

    # 4 równomiernie rozmieszczone czasy: 1/5, 2/5, 3/5, 4/5 długości
    timestamps = [
        duration * (i + 1) / (num + 1)
        for i in range(num)
    ]

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    shots = []

    for idx, ts in enumerate(timestamps, start=1):
        ts_str = format_timestamp(ts)
        shot_name = f"{base_name}_shot{idx}.png"
        shot_path = os.path.join(out_dir, shot_name)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            ts_str,
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            shot_path,
        ]
        run(cmd)
        shots.append(shot_path)

    return shots


def build_urls(filename: str):
    """Zbuduj URL pełny i miniatury."""
    base = IMGPUSH_BASE_URL.rstrip("/")
    full = f"{base}/{filename}"

    params = []
    if THUMB_WIDTH:
        params.append(f"w={THUMB_WIDTH}")
    if THUMB_HEIGHT:
        params.append(f"h={THUMB_HEIGHT}")

    if params:
        thumb = full + "?" + "&".join(params)
    else:
        thumb = full

    return full, thumb


def upload_to_imgpush(image_path: str):
    """
    Upload do imgpush:

        curl -F 'file=@/some/file.jpg' https://images.papug.it

    Odpowiedź: {"filename": "cośtam.png"}
    """
    with open(image_path, "rb") as f:
        files = {
            "file": (os.path.basename(image_path), f, "image/png"),
        }

        # można dorzucić jakieś losowe ID w razie potrzeby (raczej nie jest wymagane)
        headers = {
            "X-Upload-Session": secrets.token_hex(8),
        }

        resp = requests.post(
            IMGPUSH_BASE_URL.rstrip("/"),
            files=files,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()

    try:
        payload = resp.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Nie udało się odszyfrować JSON z imgpush: {e}\n{resp.text[:500]}"
        )

    filename = payload.get("filename")
    if not filename:
        raise RuntimeError(f"Brak pola 'filename' w odpowiedzi imgpush: {payload}")

    full_url, thumb_url = build_urls(filename)
    bbcode = f"[url={full_url}][img]{thumb_url}[/img][/url]"
    return bbcode


def main():
    parser = argparse.ArgumentParser(
        description="Generuje 4 screenshoty z wideo i wrzuca je na imgpush, zwracając BBCode miniatur."
    )
    parser.add_argument("video", help="Ścieżka do pliku wideo")

    args = parser.parse_args()
    video_path = os.path.abspath(args.video)

    if not os.path.isfile(video_path):
        print(f"Plik nie istnieje: {video_path}", file=sys.stderr)
        sys.exit(1)

    
    tmpdir = Path.cwd() / ".screenshots"
    tmpdir.mkdir()
    #tmpdir = tempfile.mkdtemp(prefix="imgpush_screens_")

    try:
        # 1. Screenshoty
        shots = make_screens(video_path, tmpdir, NUM_SHOTS)

        # 2. Uploady
        bbcodes = []
        for shot in shots:
            bb = upload_to_imgpush(shot)
            bbcodes.append(bb)

        # 3. Wypisanie BBCode – po jednym na linię
        print("[center]")
        for bb in bbcodes:
            print(bb)
        print("[/center]")

    finally:
        # Jak nie chcesz kasować screenshotów, zakomentuj to:
        # shutil.rmtree(tmpdir, ignore_errors=True)
        pass


if __name__ == "__main__":
    main()

