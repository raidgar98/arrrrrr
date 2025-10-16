#!/usr/bin/env python3
# my_script.py
import argparse
import html
import os
import re
import sys
import urllib.parse
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

RE_MP4 = re.compile(
    r'https?://stream\.vider\.info/video/\d+/v\.mp4\?uid=\d+',
    re.IGNORECASE
)

RE_EMBED = re.compile(
    r'src\s*=\s*["\'](?P<u>https?://(?:www\.)?vider\.(?:pl|info)/embed[^"\']+)["\']',
    re.IGNORECASE
)

RE_FILE_PARAM = re.compile(
    r'(?:[?&]|["\'])file=([^&"\'\s>]+)',
    re.IGNORECASE
)

def decode_multi(s: str, rounds: int = 3) -> str:
    prev = None
    cur = s
    for _ in range(rounds):
        cur = html.unescape(cur)
        dec = urllib.parse.unquote(cur)
        if dec == cur:
            break
        cur = dec
    return cur

def get(url: str, referer: str | None = None, session: requests.Session | None = None) -> requests.Response:
    sess = session or requests.Session()
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or url,
        "Connection": "keep-alive",
    }
    resp = sess.get(url, headers=headers, timeout=15, allow_redirects=True)
    resp.raise_for_status()
    return resp

def extract_mp4_from_html(html_text: str) -> str | None:
    m = RE_MP4.search(html_text)
    if m:
        return m.group(0)

    for m in RE_FILE_PARAM.finditer(html_text):
        candidate = decode_multi(m.group(1))
        m2 = RE_MP4.search(candidate)
        if m2:
            return m2.group(0)

    m = re.search(r'file\s*[:=]\s*["\']([^"\']+\.mp4\?uid=\d+)["\']', html_text, re.IGNORECASE)
    if m:
        candidate = decode_multi(m.group(1))
        m2 = RE_MP4.search(candidate)
        if m2:
            return m2.group(0)

    return None

def maybe_find_embed_url(html_text: str) -> str | None:
    m = RE_EMBED.search(html_text)
    return m.group("u") if m else None

def download_with_session(sess: requests.Session, mp4_url: str, out_path: str, referer: str):
    # jeśli out_path jest katalogiem – użyj nazwy z URL
    if os.path.isdir(out_path):
        filename = os.path.basename(urllib.parse.urlparse(mp4_url).path) or "video.mp4"
        out_path = os.path.join(out_path, filename)

    # upewnij się, że katalog docelowy istnieje
    os.makedirs(os.path.dirname(os.path.abspath(out_path) or "."), exist_ok=True)

    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Referer": referer,
        # Range wymusza 206 i zwykle przyspiesza start odtwarzania/pobierania
        "Range": "bytes=0-",
    }

    with sess.get(mp4_url, headers=headers, timeout=30, stream=True, allow_redirects=True) as r:
        r.raise_for_status()

        total = None
        # Content-Length bywa brak przy 206 – wtedy wyciągamy z Content-Range
        if r.status_code == 200 and r.headers.get("Content-Length"):
            total = int(r.headers["Content-Length"])
        elif r.status_code == 206 and r.headers.get("Content-Range"):
            try:
                total = int(r.headers["Content-Range"].split("/")[-1])
            except Exception:
                total = None

        written = 0
        chunk = 1 << 15  # 32 KiB
        with open(out_path, "wb") as f:
            for part in r.iter_content(chunk_size=chunk):
                if part:
                    f.write(part)
                    written += len(part)
                    # prosty postęp na stderr (bez zależności)
                    if total and written % (1 << 20) < chunk:  # co ~1 MiB
                        pct = written * 100 // total
                        print(f"\rPobrano: {written//1024//1024} MiB / {total//1024//1024} MiB ({pct}%)", end="", file=sys.stderr)
        if total:
            print(f"\rPobrano: {total//1024//1024} MiB (100%)", file=sys.stderr)
        print(f"Zapisano do: {out_path}", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser(description="Wyciąga direct-link MP4 i pobiera go w tej samej sesji.")
    ap.add_argument("url", help="np. https://vider.info/vid/+fxnecxs albo https://vider.pl/embed/...")
    ap.add_argument("output_path", help="Ścieżka docelowa pliku lub katalog (gdy katalog, nazwa zostanie wzięta z URL).")
    args = ap.parse_args()

    sess = requests.Session()

    try:
        # 1) pobierz stronę wejściową
        r1 = get(args.url, session=sess)
        html1 = r1.text

        # spróbuj wyciągnąć link bezpośrednio
        mp4 = extract_mp4_from_html(html1)
        referer_for_mp4 = args.url

        # 2) jeśli nie ma, spróbuj przez stronę osadzającą (embed)
        if not mp4:
            embed_url = maybe_find_embed_url(html1)
            if embed_url:
                r2 = get(embed_url, referer=args.url, session=sess)
                html2 = r2.text
                mp4 = extract_mp4_from_html(html2)
                if mp4:
                    referer_for_mp4 = embed_url

        # 3) fallback – przeskanuj wszystkie URL-e w HTML
        if not mp4:
            for url in re.findall(r'https?://[^\s"\']+', html1):
                url_dec = decode_multi(url)
                m = RE_MP4.search(url_dec)
                if m:
                    mp4 = m.group(0)
                    break

        if not mp4:
            print("Nie znalazłem linku MP4 w podanej stronie ani w osadzonym embedzie.", file=sys.stderr)
            sys.exit(2)

        # Wypisz link na stdout (zgodnie z wcześniejszym zachowaniem)
        print(mp4)

        # Pobieraj w tej samej sesji/cookies
        download_with_session(sess, mp4, args.output_path, referer=referer_for_mp4)

    except requests.HTTPError as e:
        print(f"Błąd HTTP: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Błąd sieci: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
