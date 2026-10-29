#!/usr/bin/env bash
# Repack paket resmi Termux (com.termux) agar cocok dengan prefix com.yummy,
# lalu buat repo apt "flat" di folder site/.
set -euo pipefail

OLD="com.termux"
NEW="com.yummy"   # harus 1 karakter lebih pendek dari OLD (untuk patch binary)
WORK="${WORK:-$PWD/work}"
SITE="${SITE:-$PWD/site}"
OUT="$SITE/debs"

repack() {
  local deb="$1" name d f t n
  name="$(basename "$deb" .deb)"
  d="$WORK/x/$name"
  rm -rf "$d"; mkdir -p "$d"
  dpkg-deb -R "$deb" "$d"

  # 1) pindahkan folder data/data/com.termux -> com.yummy
  if [ -d "$d/data/data/$OLD" ]; then
    mv "$d/data/data/$OLD" "$d/data/data/$NEW"
  fi

  # 2) symlink absolut yang menunjuk ke prefix lama
  while IFS= read -r -d '' f; do
    t="$(readlink "$f")"
    case "$t" in
      *"/data/data/$OLD"*)
        n="$(printf '%s' "$t" | sed "s|/data/data/$OLD|/data/data/$NEW|g")"
        ln -sfn "$n" "$f" ;;
    esac
  done < <(find "$d" -type l -print0)

  # 3) isi file: teks diganti biasa, binary diganti dengan panjang SAMA
  #    (/data/data/com.termux -> /data/data/com.yummy/ ; slash ganda tetap valid)
  while IFS= read -r -d '' f; do
    if grep -qI . "$f" 2>/dev/null; then
      sed -i "s|/data/data/$OLD|/data/data/$NEW|g" "$f"
    else
      LC_ALL=C perl -0777 -pi -e 's|/data/data/com\.termux|/data/data/com.yummy/|g' "$f"
    fi
  done < <(grep -rlaFZ "/data/data/$OLD" "$d" || true)

  # 4) md5sums harus dihitung ulang
  if [ -f "$d/DEBIAN/md5sums" ]; then
    ( cd "$d" && find . -path ./DEBIAN -prune -o -type f -print0 \
        | sort -z | xargs -0 -r md5sum | sed 's| \./| |' ) > "$d/DEBIAN/md5sums"
  fi

  # 5) laporan sisa string lama
  if grep -rlaF "/data/data/$OLD" "$d" >/dev/null 2>&1; then
    echo "[!] masih ada /data/data/$OLD di $name" >> "$WORK/report.txt"
  fi
  grep -rIn "$OLD" "$d" 2>/dev/null | grep -v "$OLD\." | head -3 \
    | sed "s|^$d/||" >> "$WORK/report.txt" || true

    # 6) izin script maintainer harus 0555-0775 (paket Termux memakai 700)
  chmod 0755 "$d" "$d/DEBIAN"
  for s in preinst postinst prerm postrm config; do
    if [ -f "$d/DEBIAN/$s" ]; then chmod 0755 "$d/DEBIAN/$s"; fi
  done

  # 7) bangun ulang .deb
  mkdir -p "$OUT"
  dpkg-deb --root-owner-group -Zxz -b "$d" "$OUT/$(basename "$deb")" >/dev/null
  rm -rf "$d"
}

main() {
  mkdir -p "$WORK/dl" "$OUT"
  : > "$WORK/report.txt"
  python3 scripts/resolve.py > "$WORK/list.txt"

  while read -r name url; do
    echo "==> $name"
    f="$WORK/dl/$(basename "$url")"
    curl -fsSL --retry 5 --retry-delay 3 -o "$f" "$url"
    repack "$f"
    rm -f "$f"
  done < "$WORK/list.txt"

  # --- indeks repo apt (flat) ---
  cd "$SITE"
  apt-ftparchive packages debs > Packages
  gzip -9kf Packages
  apt-ftparchive \
    -o APT::FTPArchive::Release::Origin=Yummy \
    -o APT::FTPArchive::Release::Label=Yummy \
    -o APT::FTPArchive::Release::Architectures=aarch64 \
    release . > ../Release.tmp
  mv ../Release.tmp Release
  cat > index.html <<HTML
<!doctype html><meta charset=utf-8><title>Yummy repo</title>
<p>Tambahkan ke sources.list:</p>
<pre>deb [trusted=yes] https://raflysyahr.github.io/yummy-repo/ ./</pre>
HTML
  echo "Selesai: $(ls debs | wc -l) paket."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
