#!/usr/bin/env bash
# Bootstrap-script för skarmar-kiosk på Raspberry Pi OS Bookworm Desktop (X11)
# Kör som pi-användaren: bash install.sh
set -euo pipefail

KIOSK_USER="${SUDO_USER:-$(whoami)}"
KIOSK_ENV="/etc/skarmar/kiosk.env"
AUTOSTART_DIR="/home/${KIOSK_USER}/.config/lxsession/LXDE-pi"
AUTOSTART_FILE="${AUTOSTART_DIR}/autostart"

# --- 1. Fråga efter skärm-URL ---
if [[ -f "$KIOSK_ENV" ]]; then
  echo "Befintlig konfiguration hittad: $KIOSK_ENV"
  cat "$KIOSK_ENV"
  read -rp "Ange ny SCREEN_URL (lämna tomt för att behålla befintlig): " INPUT_URL
else
  read -rp "Ange SCREEN_URL (t.ex. https://skarmar.svky.se/s/kyrkan): " INPUT_URL
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

# --- 2. Tvinga X11 (stäng av Wayland i lightdm) ---
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
if grep -q "^#\?WaylandEnable" "$LIGHTDM_CONF" 2>/dev/null; then
  sudo sed -i 's/^#\?WaylandEnable.*/WaylandEnable=false/' "$LIGHTDM_CONF"
else
  echo "[Seat:*]" | sudo tee -a "$LIGHTDM_CONF" > /dev/null
  echo "WaylandEnable=false" | sudo tee -a "$LIGHTDM_CONF" > /dev/null
fi
echo "-> Wayland avstängt"

# --- 3. Autologin för kiosk-användaren ---
sudo raspi-config nonint do_boot_behaviour B4
echo "-> Autologin till skrivbord aktiverat"

# --- 4. Installera chromium om det saknas ---
if ! command -v chromium-browser &>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y chromium-browser
fi

# --- 5. Skapa autostart ---
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_FILE" <<'AUTOSTART'
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xset s off
@xset -dpms
@xset s noblank
@/usr/local/bin/skarmar-kiosk-launch
AUTOSTART
echo "-> Autostart skriven: $AUTOSTART_FILE"

# --- 6. Skapa start-wrapper (väntar på NTP + nät) ---
sudo tee /usr/local/bin/skarmar-kiosk-launch > /dev/null <<'LAUNCHER'
#!/usr/bin/env bash
# Vänta på nätverket (max 60s)
for i in $(seq 1 12); do
  if ping -c1 -W2 8.8.8.8 &>/dev/null; then
    break
  fi
  sleep 5
done

# Vänta på NTP-synk (max 60s) — krävs för klocka-widgeten
for i in $(seq 1 12); do
  if timedatectl show --property=NTPSynchronized --value 2>/dev/null | grep -q yes; then
    break
  fi
  sleep 5
done

# Rensa eventuell krasch-flagga från senaste session
rm -f /home/"$(whoami)"/.config/chromium/SingletonLock

source /etc/skarmar/kiosk.env

exec chromium-browser \
  --kiosk \
  --app="${SCREEN_URL}" \
  --noerrdialogs \
  --disable-infobars \
  --disable-features=Translate,OverscrollHistoryNavigation \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --no-first-run
LAUNCHER

sudo chmod +x /usr/local/bin/skarmar-kiosk-launch
echo "-> Launcher skriven: /usr/local/bin/skarmar-kiosk-launch"

# --- 7. Dölj muspekaren (kräver unclutter) ---
if ! command -v unclutter &>/dev/null; then
  sudo apt-get install -y unclutter
fi
# Lägg till i autostart om det inte redan finns
if ! grep -q unclutter "$AUTOSTART_FILE"; then
  echo "@unclutter -idle 1 -root" >> "$AUTOSTART_FILE"
fi

echo ""
echo "Klar! Starta om Pi:n för att aktivera kiosk-läget:"
echo "  sudo reboot"
