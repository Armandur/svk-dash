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

**På RPi 4B med 1 GB RAM är rotation mellan flera videor en återvänds-
gränd.** Efter att ha testat ett stort antal kombinationer landade
slutsatsen i att V4L2-hårdvarudekodern (`bcm2835-codec-decode` på
`/dev/video10`) bara stödjer **en aktiv H.264-ström åt gången**, och
kan inte växla mellan strömmar utan att antingen krascha GPU-processen
eller lämna osynliga video-ytor.

### Vad som testats (och varför inget fungerade helt)

Med hwaccel-flaggor påslagna (`/etc/chromium.d/10-hwdecode` med
`--enable-features=AcceleratedVideoDecodeLinuxGL`, `--ignore-gpu-blocklist`,
`--use-gl=egl`) öppnas V4L2-dekodern, men:

| Rotationsstrategi | Resultat |
|---|---|
| `v.src = ''` + `v.load()` vid pause + återsatt `src` vid play | GPU-processen kraschar 3+ gånger/min |
| Statisk `src` + lata init (`data-src` → `src` första gången) | Samma kraschmönster, drone/fågel blir vita mellan krascher |
| Statisk `src` + `autoplay`, opacity styr synlighet | 0 krascher, men bara en video spelar (V4L2 tar första som vinner race), övriga vita |
| Statisk `src`, inget `autoplay`, JS styr `play()/pause()` | 0 krascher, men bara senaste `play()`-ade videon spelar |
| Samma + `preload="none"` | Samma mönster, flimmer mellan vyer |
| Samma + `v.load()` innan `v.play()` i rotation | Kraschar igen (load → V4L2 teardown) |

Allt testat både i 2560×1440 CVT och 1920×1080 CEA, med de tre
drone/murana/fågel-videorna och 720p-varianter (1.5 Mbps). Samma
mönster i båda.

### Slutsats

- **För kiosker med videorotation på RPi 4B 1 GB: kör mjukvarudekod.**
  Det är default i projektet (inga flaggor i `/etc/chromium.d/`).
  Videorna laggar på 1080p men kraschar inte.
- **RPi 4B med 2+ GB RAM kan klara hwaccel** — inte verifierat här,
  men V3D-minnestrycket är sannolikt det som triggar krascherna, och
  det är mer tillgängligt på större modeller. Är det relevant: börja
  med endast `--enable-features=AcceleratedVideoDecodeLinuxGL` och
  `--ignore-gpu-blocklist` i `/etc/chromium.d/`.

### Knep för att minska laggen vid mjukvarudekod

- Transcoda videorna till 720p @ ~1.5 Mbps:
  ```bash
  ffmpeg -i in.mp4 -vf scale=-2:720 -c:v libx264 -b:v 1.5M \
      -movflags +faststart out.mp4
  ```
- Ha bara *en* video per vy och rotera mellan vyerna (samtidiga
  videor i DOM tävlar om samma dekod-pipeline).

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
