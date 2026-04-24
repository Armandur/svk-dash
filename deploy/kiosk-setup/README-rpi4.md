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

**På RPi 4B med 1 GB RAM är videouppspelning en återvändsgränd.** V4L2-
dekodern finns (`bcm2835-codec-decode` på `/dev/video10`) och Chromium
rapporterar `video_decode: enabled` i `chrome://gpu`, men den öppnas
aldrig av sig själv — dekodningen sker i mjukvara och videorna laggar.
Mätt via `fuser /dev/video1[0-2]` och fd:er i gpu-processen.

Försök att tvinga fram V4L2 med dessa flaggor:
```
--enable-features=AcceleratedVideoDecodeLinuxGL
--ignore-gpu-blocklist
--use-gl=egl
```
gjorde att dekodern öppnades (`fuser` visade PID på `/dev/video10`),
men GPU-processen kraschade inom sekunder — flera crashdumps per minut
i `~/.config/chromium/Crash Reports/pending/`. Det gällde även efter
att skärmupplösningen sänkts till 1920×1080 och videoscaling eliminerats.
Orsaken är sannolikt att 1 GB RAM + V3D-drivrutinen inte räcker för
kombinationen GPU-compositing + hårdvarudekod på Trixie.

Varianter som testats och som alla ger samma kraschmönster:
- Med och utan `AcceleratedVideoDecodeLinuxZeroCopyGL`
- ANGLE (`--use-angle=gles`) vs rå EGL (`--use-gl=egl`)
- Skärm i 2560×1440 CVT respektive 1920×1080 CEA

**Slutsats:** mjukvarudekodning är det enda stabila alternativet på
RPi 4B 1 GB. Acceptera lagg, eller byt till en RPi 4B med 2+ GB RAM
(där V4L2-vägen rapporteras fungera — ej verifierat i detta projekt).

Knep som kan hjälpa marginellt vid mjukvarudekodning:
- Transcoda videorna till 720p + låg bitrate (~1.5 Mbps) så mjukvaru-
  dekodern hinner med. `ffmpeg -i in.mp4 -vf scale=-2:720 -c:v libx264 -b:v 1.5M -movflags +faststart out.mp4`
- Ha bara en video per vy och rotera mellan dem (samtidiga videor
  tävlar om samma enda GPU-dekodning-pipeline)

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
