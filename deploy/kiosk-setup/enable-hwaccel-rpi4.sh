#!/usr/bin/env bash
# Aktivera V4L2-hårdvarudekod av video i Chromium på RPi 4B.
#
# OBS: Kombinationen Chromium 147 + Mesa V3D + Trixie + flera <video>-taggar
# i DOM:et har visat sig krascha GPU-processen återkommande. Det räcker att
# DOM:et innehåller flera videor — JS-rotationen som visar en åt gången hjälper
# inte. Scriptet är därför endast lämpligt för skärmar där kanalen totalt
# innehåller en (1) video-widget. Sätt skärmen till "Videokapacitet: En video
# totalt" i admin; admin varnar om kanalen bryter regeln.
#
# Användning på Pi:n:
#   sudo bash enable-hwaccel-rpi4.sh
# Backa ut:
#   sudo rm /etc/chromium.d/10-hwdecode && pkill -x chromium
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Måste köras som root (kör med sudo)." >&2
    exit 1
fi

CFG=/etc/chromium.d/10-hwdecode

cat > "$CFG" <<'EOF'
--enable-features=AcceleratedVideoDecodeLinuxGL
--ignore-gpu-blocklist
--use-gl=egl
EOF

chmod 644 "$CFG"
echo "Skrev $CFG:"
cat "$CFG"
echo
echo "Starta om chromium för att flaggorna ska gälla:"
echo "  pkill -x chromium"
echo
echo "Verifiera att V4L2-dekodern öppnas (medan en video spelar):"
echo "  fuser /dev/video10 /dev/video11 /dev/video12 /dev/video18"
