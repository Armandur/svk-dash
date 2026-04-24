#!/usr/bin/env bash
# Bootstrap-script för skarmar-kiosk på Raspberry Pi OS Bookworm Desktop
# Kör som pi-användaren: bash install.sh
set -euo pipefail

KIOSK_USER="${SUDO_USER:-$(whoami)}"
KIOSK_ENV="/etc/skarmar/kiosk.env"

# --- 1. Fråga efter skärm-URL ---
if [[ -f "$KIOSK_ENV" ]]; then
  echo "Befintlig konfiguration hittad:"
  cat "$KIOSK_ENV"
  read -rp "Ange ny SCREEN_URL (lämna tomt för att behålla befintlig): " INPUT_URL
else
  read -rp "Ange SCREEN_URL (t.ex. http://192.168.1.42:8000/s/kyrkan): " INPUT_URL
fi

if [[ -n "$INPUT_URL" ]]; then
  sudo mkdir -p /etc/skarmar
  echo "SCREEN_URL=${INPUT_URL}" | sudo tee "$KIOSK_ENV" > /dev/null
  echo "-> Sparad: $KIOSK_ENV"
fi

source "$KIOSK_ENV"

if [[ -z "${SCREEN_URL:-}" ]]; then
  echo "Fel: SCREEN_URL saknas i $KIOSK_ENV" >&2
  exit 1
fi

# --- 2. Fråga om pekskärm ---
read -rp "Har Pi:n en pekskärm? (j/n): " TOUCH_ANSWER
TOUCH_FLAG=""
if [[ "${TOUCH_ANSWER,,}" == "j" ]]; then
  TOUCH_FLAG="  --touch-events=enabled \\"$'\n'
fi

# --- 3. Identifiera Pi-modell och sätt prestandaflaggor ---
PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo "unknown")
echo "-> Hårdvara: $PI_MODEL"

VAAPI_FLAGS=""
GPU_MEM=128
if echo "$PI_MODEL" | grep -q "Raspberry Pi 4\|Raspberry Pi 5"; then
  # RPi 4/5: VA-API fungerar, 64-bit OS rekommenderas
  VAAPI_FLAGS="  --enable-features=VaapiVideoDecoder,VaapiVideoDecodeLinuxGL \\"$'\n'"  --use-gl=egl \\"$'\n'"  --ignore-gpu-blocklist \\"$'\n'
  GPU_MEM=256
fi

# --- 4. GPU-minne ---
BOOT_CONFIG="/boot/firmware/config.txt"
if ! grep -q "^gpu_mem=" "$BOOT_CONFIG" 2>/dev/null; then
  echo "gpu_mem=${GPU_MEM}" | sudo tee -a "$BOOT_CONFIG" > /dev/null
else
  sudo sed -i "s/^gpu_mem=.*/gpu_mem=${GPU_MEM}/" "$BOOT_CONFIG"
fi
echo "-> gpu_mem=${GPU_MEM} i $BOOT_CONFIG"

# Extrahera host för nät-ping
PING_HOST=$(echo "$SCREEN_URL" | sed 's|https\?://||; s|[:/].*||')

# --- 5. Installera paket ---
PKGS=()
command -v chromium-browser &>/dev/null || PKGS+=(chromium-browser)
command -v unclutter &>/dev/null        || PKGS+=(unclutter)
if [[ ${#PKGS[@]} -gt 0 ]]; then
  sudo apt-get update -qq
  sudo apt-get install -y "${PKGS[@]}"
fi

# --- 6. Autologin via getty på tty1 (kringgår lightdm) ---
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf > /dev/null <<UNIT
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${KIOSK_USER} --noclear %I \$TERM
UNIT

# Starta X automatiskt vid inloggning på tty1
cat > "/home/${KIOSK_USER}/.bash_profile" <<'PROFILE'
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor
fi
PROFILE

# xinitrc: skärmsläckare av, dölj muspekare, starta kiosk
cat > "/home/${KIOSK_USER}/.xinitrc" <<'XINITRC'
#!/bin/bash
xset s off
xset -dpms
xset s noblank
unclutter -idle 1 -root &
exec /usr/local/bin/skarmar-kiosk-launch
XINITRC
chmod +x "/home/${KIOSK_USER}/.xinitrc"

# Stäng av lightdm så den inte konkurrerar
sudo systemctl disable lightdm 2>/dev/null || true
echo "-> Autologin via getty konfigurerat"

# --- 7. Skapa launcher ---
sudo tee /usr/local/bin/skarmar-kiosk-launch > /dev/null <<LAUNCHER
#!/usr/bin/env bash
source /etc/skarmar/kiosk.env

PING_HOST="${PING_HOST}"

# Vänta på nätverket (max 60s)
for i in \$(seq 1 12); do
  if ping -c1 -W2 "\${PING_HOST}" &>/dev/null; then break; fi
  sleep 5
done

# Försök synka NTP, hoppa över om det tar för lång tid
for i in \$(seq 1 6); do
  if timedatectl show --property=NTPSynchronized --value 2>/dev/null | grep -q yes; then break; fi
  sleep 5
done

rm -f /home/"\$(whoami)"/.config/chromium/SingletonLock

exec chromium-browser \\
  --kiosk \\
  --app="\${SCREEN_URL}" \\
${TOUCH_FLAG}${VAAPI_FLAGS}  --noerrdialogs \\
  --disable-infobars \\
  --disable-features=Translate,TranslateUI,OverscrollHistoryNavigation,HardwareMediaKeyHandling \\
  --disable-session-crashed-bubble \\
  --disable-dev-shm-usage \\
  --check-for-update-interval=31536000 \\
  --no-first-run
LAUNCHER

sudo chmod +x /usr/local/bin/skarmar-kiosk-launch
echo "-> Launcher skriven: /usr/local/bin/skarmar-kiosk-launch"

# --- 8. Chromium managed policy: stäng av translate ---
sudo mkdir -p /etc/chromium/policies/managed
sudo tee /etc/chromium/policies/managed/kiosk.json > /dev/null <<'POLICY'
{
  "TranslateEnabled": false
}
POLICY
echo "-> Chromium policy: TranslateEnabled=false"

echo ""
echo "Klar! Starta om Pi:n för att aktivera kiosk-läget:"
echo "  sudo reboot"
