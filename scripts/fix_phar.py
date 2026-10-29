#!/usr/bin/env python3
"""Hitung ulang tanda tangan phar (md5/sha1/sha256/sha512) setelah isinya di-patch.
Pemakaian: fix_phar.py <file>. Tidak melakukan apa-apa kalau bukan phar."""
import hashlib
import sys

ALGOS = {1: ("md5", 16), 2: ("sha1", 20), 3: ("sha256", 32), 4: ("sha512", 64)}


def main(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.endswith(b"GBMB") or len(data) < 12:
        return
    flags = int.from_bytes(data[-8:-4], "little")
    if flags not in ALGOS:
        print("[!] phar %s memakai tanda tangan jenis %s, dilewati" % (path, hex(flags)), file=sys.stderr)
        return
    name, size = ALGOS[flags]
    body = data[: -8 - size]
    sig = hashlib.new(name, body).digest()
    new = body + sig + data[-8:]
    if new != data:
        with open(path, "wb") as fh:
            fh.write(new)
        print("[phar] tanda tangan dihitung ulang: " + path)


if __name__ == "__main__":
    main(sys.argv[1])
