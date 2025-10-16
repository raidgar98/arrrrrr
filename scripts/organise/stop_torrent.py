from __future__ import annotations

import sys
import xmlrpc.client

def update_directory_and_save(infohash: str):
    """
    Ustaw katalog torrenta i zapisz całą sesję w jednym multicall.
    Zwraca listę odpowiedzi metod XML-RPC.

    :param infohash: 40-znakowy hash (hex)
    :param basedir:  docelowy katalog (istniejący lub do utworzenia przez rTorrent/Twoje procesy)
    """
    if infohash == "noop":
        return None
    ih = infohash.strip().lower()
    if not (len(ih) == 40 and all(c in "0123456789abcdef" for c in ih)):
        raise ValueError("infohash musi być 40-znakowym ciągiem hex.")

    server = xmlrpc.client.ServerProxy("http://127.0.0.1:8000/RPC2", allow_none=True)
    calls = [
        {"methodName": "d.stop",       "params": [ih]},
        {"methodName": "session.save",    "params": []},
    ]
    print("sending:", calls)
    return server.system.multicall(calls)


if __name__ == "__main__":
    print(update_directory_and_save(sys.argv[1].strip(" \t")))
