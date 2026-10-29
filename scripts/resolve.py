#!/usr/bin/env python3
"""Cari paket di indeks resmi Termux + dependensinya.
Output (stdout): "<nama> <url .deb>" satu baris per paket. Peringatan ke stderr."""
import gzip
import re
import subprocess
import sys
import urllib.request

MIRROR = "https://packages.termux.dev/apt/termux-main"
INDEX = MIRROR + "/dists/stable/main/binary-aarch64/Packages"


def warn(msg):
    print("[!] " + msg, file=sys.stderr)


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def load_index():
    import os
    if os.environ.get("INDEX_FILE"):
        with open(os.environ["INDEX_FILE"]) as fh:
            return fh.read()
    try:
        return fetch(INDEX).decode("utf-8")
    except Exception as e:  # coba versi .gz
        warn("Packages polos gagal (%s), coba .gz" % e)
        return gzip.decompress(fetch(INDEX + ".gz")).decode("utf-8")


def version_gt(a, b):
    return subprocess.run(["dpkg", "--compare-versions", a, "gt", b]).returncode == 0


def parse(text):
    pkgs = {}
    for block in text.split("\n\n"):
        f, key = {}, None
        for line in block.splitlines():
            if not line.strip():
                continue
            if line[0] in " \t":
                if key:
                    f[key] += "\n" + line
            else:
                k, _, v = line.partition(":")
                key = k.strip()
                f[key] = v.strip()
        name = f.get("Package")
        if not name:
            continue
        old = pkgs.get(name)
        if old is None or version_gt(f.get("Version", "0"), old.get("Version", "0")):
            pkgs[name] = f
    return pkgs


def read_list(path):
    out = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    out.append(line)
    except FileNotFoundError:
        warn("file %s tidak ada" % path)
    return out


def dep_groups(f):
    groups = []
    for fld in ("Pre-Depends", "Depends"):
        for part in f.get(fld, "").split(","):
            alts = [re.sub(r"\(.*?\)|:\w+", "", a).strip() for a in part.split("|")]
            alts = [a for a in alts if a]
            if alts:
                groups.append(alts)
    return groups


def main():
    pkgs = parse(load_index())
    provides = {}
    for name, f in pkgs.items():
        for p in f.get("Provides", "").split(","):
            p = re.sub(r"\(.*?\)", "", p).strip()
            if p:
                provides.setdefault(p, name)

    def real_name0(n):
        if n in pkgs:
            return n
        return provides.get(n)

    # Semua paket bootstrap + dependensinya otomatis dikecualikan
    exclude = set(read_list("exclude.txt"))
    bq = list(read_list("bootstrap-packages.txt"))
    while bq:
        n = bq.pop(0)
        r = real_name0(n)
        if r is None or r in exclude:
            continue
        exclude.add(r)
        for alts in dep_groups(pkgs[r]):
            for a in alts:
                if real_name0(a):
                    bq.append(a)
                    break
    warn("paket bootstrap yang dikecualikan: %d" % len(exclude))
    queue = list(read_list("packages.txt"))
    seen, result = set(), []

    def real_name(n):
        if n in pkgs:
            return n
        return provides.get(n)

    while queue:
        n = queue.pop(0)
        real = real_name(n)
        if real is None:
            warn("paket tidak ditemukan di indeks: " + n)
            continue
        if real in seen or real in exclude:
            continue
        seen.add(real)
        f = pkgs[real]
        result.append((real, MIRROR + "/" + f["Filename"]))
        for alts in dep_groups(f):
            if any(a in exclude or real_name(a) in exclude for a in alts):
                continue  # sudah dipenuhi bootstrap
            for a in alts:
                if real_name(a):
                    queue.append(a)
                    break
            else:
                warn("dependensi tak terselesaikan %s -> %s" % (real, "|".join(alts)))

    for name, url in result:
        print(name, url)
    warn("total paket yang akan direpack: %d" % len(result))


if __name__ == "__main__":
    main()
