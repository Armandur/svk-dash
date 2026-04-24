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

# Extrahera host för nät-ping (t.ex. 192.168.1.42 ur http://192.168.1.42:8000/s/foo)
PING_HOST=$(echo "$SCREEN_URL" | sed 's|https\?://||; s|[:/].*||')

# --- 2. Tvinga X11, autologin och autologin-gruppen ---
# Lägg till användaren i autologin-gruppen (krävs av lightdm)
sudo addgroup --system autologin 2>/dev/null || true
sudo usermod -aG autologin "$KIOSK_USER"

# Skriv en ren lightdm.conf med ett enda [Seat:*]-block
sudo tee /etc/lightdm/lightdm.conf > /dev/null <<LIGHTDMEOF
[LightDM]

[Seat:*]
greeter-session=pi-greeter-labwc
greeter-hide-users=false
user-session=LXDE-pi
display-setup-script=/usr/share/dispsetup.sh
autologin-user=${KIOSK_USER}
autologin-session=LXDE-pi
WaylandEnable=false

[XDMCPServer]
[VNCServer]
LIGHTDMEOF
echo "-> lightdm.conf skriven (X11, autologin)"

# --- 4. Installera chromium och unclutter om de saknas ---
PKGS=()
command -v chromium-browser &>/dev/null || PKGS+=(chromium-browser)
command -v unclutter &>/dev/null        || PKGS+=(unclutter)
if [[ ${#PKGS[@]} -gt 0 ]]; then
  sudo apt-get update -qq
  sudo apt-get install -y "${PKGS[@]}"
fi

# --- 5. Skapa autostart ---
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_FILE" <<'AUTOSTART'
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 1 -root
@/usr/local/bin/skarmar-kiosk-launch
AUTOSTART
echo "-> Autostart skriven: $AUTOSTART_FILE"

# --- 6. Skapa start-wrapper ---
sudo tee /usr/local/bin/skarmar-kiosk-launch > /dev/null <<LAUNCHER
#!/usr/bin/env bash
source /etc/skarmar/kiosk.env

PING_HOST="${PING_HOST}"

# Vänta på nätverket — pinga servern direkt (max 60s)
for i in \$(seq 1 12); do
  if ping -c1 -W2 "\${PING_HOST}" &>/dev/null; then
    break
  fi
  sleep 5
done

# Försök synka NTP — hoppa över om det tar för lång tid (inget internet nödvändigt)
for i in \$(seq 1 6); do
  if timedatectl show --property=NTPSynchronized --value 2>/dev/null | grep -q yes; then
    break
  fi
  sleep 5
done

# Rensa eventuell krasch-flagga
rm -f /home/"\$(whoami)"/.config/chromium/SingletonLock

exec chromium-browser \\
  --kiosk \\
  --app="\${SCREEN_URL}" \\
  --touch-events=enabled \\
  --noerrdialogs \\
  --disable-infobars \\
  --disable-features=Translate,TranslateUI,OverscrollHistoryNavigation,HardwareMediaKeyHandling \\
  --disable-session-crashed-bubble \\
  --disable-dev-shm-usage \\
  --check-for-update-interval=31536000 \\
  --no-first-run
LAUNCHER

sudo chmod +x /usr/local/bin/skarmar-kiosk-launch
echo "-> Launcher skriven: /usr/local/bin/skarmar-kiosk-launch"

# --- 7. Chromium-inställningar: stäng av translate ---
PREF_DIR="/home/${KIOSK_USER}/.config/chromium/Default"
mkdir -p "$PREF_DIR"
PREF_FILE="${PREF_DIR}/Preferences"
if [ ! -f "$PREF_FILE" ]; then
  echo '{"translate":{"enabled":false},"translate_blocked_languages":["sv"]}' > "$PREF_FILE"
fi
echo "-> Chromium translate avstängt"

echo ""
echo "Klar! Starta om Pi:n för att aktivera kiosk-läget:"
echo "  sudo reboot"
