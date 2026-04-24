# skarmar – Pi-kiosk, RPi 4B med HDMI-skärm

Konfiguration testad på **Raspberry Pi 4B** med extern **HDMI-skärm**
och utan pekskärm.

---

## Skillnader mot RPi 3B-setup

| | RPi 3B + DSI Touch Display | RPi 4B + HDMI |
|---|---|---|
| OS | 32-bit Bookworm Desktop | **64-bit** Bookworm Desktop |
| Pekskärm | `--touch-events=enabled` | Utan |
| Skärmrotation | `lcd_rotate` i config.txt | `display_rotate` eller HDMI-inställningar |
| Video (1080p) | Laggar (mjukvarudekodning) | Laggar (se nedan) |
| `gpu_mem` | 128 | **256** |

`install.sh` detekterar automatiskt RPi 4B och sätter rätt flaggor och
GPU-minne. Det frågar också om pekskärm — svara **n** för HDMI-setup.

---

## Steg 1 – Flasha OS

Använd **Raspberry Pi Imager** och välj:
- **OS:** Raspberry Pi OS (64-bit) – Trixie Desktop (eller Bookworm om det finns)
- **Lagring:** ditt SD-kort

Klicka på kugghjulet och konfigurera:
- Hostname (t.ex. `kiosk-hall`)
- Aktivera SSH
- Användare: `pi` + lösenord

---

## Steg 2 – Skapa en skärm i admin

Gå till `http://192.168.1.42:8000/admin/screens` och skapa en ny skärm.
Kiosk-URL:en blir t.ex.:

```
http://192.168.1.42:8000/s/hall
```

---

## Steg 3 – Installera kiosk

```bash
scp install.sh pi@<pi-ip>:~/
ssh pi@<pi-ip>
bash install.sh
# SCREEN_URL: http://192.168.1.42:8000/s/hall
# Pekskärm: n
sudo reboot
```

---

## HDMI-upplösning

RPi 4B har två Micro HDMI-portar. Den som sitter **närmast USB-C-strömkontakten**
är primärporten (HDMI-1). Den andra (HDMI-2) kan ge bättre kompatibilitet
med vissa skärmar — prova den om du inte får bild efter POST.

Upplösning läses automatiskt via HDMI EDID — brukar fungera utan
konfiguration. Om skärmen visar fel upplösning, lägg till i
`/boot/firmware/config.txt` under `[all]`:

```ini
# Exempel: 1920x1080 @ 60 Hz
hdmi_group=2
hdmi_mode=82
```

Vanliga värden för `hdmi_mode` (med `hdmi_group=2`):
- `16` = 1080p 60Hz
- `82` = 1080p 60Hz (alias)
- `87` = anpassad (kräver `hdmi_cvt`)

---

## Videouppspelning

På RPi 4B finns en V4L2-dekoder (`bcm2835-codec-decode` på
`/dev/video10`). Chromium på Trixie stöder den via flaggor, men
kombinationen **1 GB RAM + 1440p-compositing + HW-dekod** är instabil
— GPU-processen kraschar återkommande (flera crashdumps per minut) och
videorna flimrar. Sekventiell uppspelning med mjukvarudekod är därför
default — videorna laggar men kraschar inte.

Om du har en RPi 4B med **2+ GB RAM** eller en **skärm på 1080p eller
lägre**, kan du prova att aktivera V4L2-dekodern:

```bash
sudo sh -c 'cat > /etc/chromium.d/10-hwdecode' <<EOF
--enable-features=AcceleratedVideoDecodeLinuxGL
--ignore-gpu-blocklist
--use-gl=egl
EOF
pkill -x chromium
```

Verifiera att dekodern öppnas (medan en video spelar):
```bash
fuser /dev/video10 /dev/video11 /dev/video12 /dev/video18
# Ska visa en PID på /dev/video10
```

Om `fuser` visar PID i några sekunder och sedan tomt = GPU-processen
har kraschat. Backa ut flaggorna igen:
```bash
sudo rm /etc/chromium.d/10-hwdecode
pkill -x chromium
```

### Tips: håll skärmupplösningen ≤ videons upplösning

Video som upscalas i realtid (1080p → 1440p/4K) kostar extra på
V3D-GPU:n. Använd skärmens native-upplösning och se till att videorna
i mediebiblioteket är ≤ den upplösningen. H.264 main/high profile
@ 1920×1080 är max som V4L2-dekodern stöder.

---

## Byta skärm-URL efteråt

```bash
sudo nano /etc/skarmar/kiosk.env
sudo reboot
```

---

## Felsökning

**Svart skärm:**
```bash
DISPLAY=:0 /usr/local/bin/skarmar-kiosk-launch &
```

**Kontrollera att hårdvarudekodning används:**
Öppna `chrome://gpu` i adressfältet och sök efter
`Video Decode: Hardware accelerated`. På RPi 4B är statusen oftast
`enabled`, men dekodern öppnas inte per automatik — se avsnittet
"Videouppspelning" nedan.

**Fel upplösning:**
```bash
# Visa tillgängliga lägen:
tvservice -m DMT
tvservice -m CEA
```
