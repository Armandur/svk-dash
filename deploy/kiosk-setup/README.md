# skarmar – Pi-kiosk bootstrap

Testat på **Raspberry Pi 3B** med officiell **RPi Touch Display (800×480)**
och **Raspberry Pi OS Bookworm Desktop** (X11, inte Wayland).

> **Obs:** Denna konfiguration är specifik för RPi Touch Display via DSI.
> För RPi med extern HDMI-skärm och utan pekskärm behöver troligen dessa
> saker justeras:
> - Ta bort `--touch-events=enabled` ur Chromium-flaggorna
> - `lcd_rotate` i `/boot/firmware/config.txt` gäller bara DSI-displayen —
>   för HDMI används `display_rotate` eller `video=` i kernel-parametrar
> - Upplösning sätts automatiskt via HDMI EDID men kan behöva fixas med
>   `hdmi_group` och `hdmi_mode` i `/boot/firmware/config.txt`

---

## Känd begränsning: video på RPi 3B

RPi 3B (32-bit ARM, VideoCore IV) saknar VA-API-stöd i modern Chromium.
**Video i 1080p laggar** även med `gpu_mem=128` och Vaapi-flaggor — det
faller alltid tillbaka till mjukvarudekodning på Cortex-A53.

Fungerar bra på RPi 3B:
- Klocka, kalender, markdown, bilder, bildspel

Funkar inte smidigt:
- MP4-video i 1080p (lagg)
- MP4-video i 720p (möjligt men känsligt för bitrate)

För videotung kiosk: använd **RPi 4 eller 5** som har fungerande
hardware-decoding i Chromium.

Workaround om du ändå vill köra video: konvertera till 480p på servern:
```bash
ffmpeg -i original.mp4 -vf scale=854:480 -c:v libx264 -preset fast -crf 28 -an output_480p.mp4
```
RPi Touch Display är 800×480 native — ingen synlig kvalitetsförlust.

---

## Steg 1 – Flasha OS

Använd **Raspberry Pi Imager** och välj:
- **OS:** Raspberry Pi OS (32-bit) – Bookworm Desktop
- **Lagring:** ditt SD-kort

Klicka på kugghjulet och konfigurera:
- Hostname (t.ex. `kiosk-kyrkan`)
- Aktivera SSH
- Användare: `pi` + lösenord
- Ethernet rekommenderas framför WiFi

---

## Steg 2 – Skapa en skärm i admin

Gå till `http://192.168.1.42:8000/admin/screens` och skapa en ny skärm.
Notera slugen (t.ex. `kyrkan`). Kiosk-URL:en blir:

```
http://192.168.1.42:8000/s/kyrkan
```

---

## Steg 3 – Installera kiosk

Kopiera `install.sh` till Pi:n och kör:

```bash
scp install.sh pi@<pi-ip>:~/
ssh pi@<pi-ip>
bash install.sh
# Ange: http://192.168.1.42:8000/s/kyrkan
sudo reboot
```

---

## Vad scriptet gör

1. Sparar `SCREEN_URL` i `/etc/skarmar/kiosk.env`
2. Lägger `pi` i autologin-gruppen och skriver en ren `lightdm.conf`
3. Konfigurerar getty-autologin på tty1 + `startx` (kringgår lightdm)
4. Installerar `chromium-browser` och `unclutter` vid behov
5. Skriver `/usr/local/bin/skarmar-kiosk-launch` som:
   - Väntar på att servern svarar på ping (max 60s)
   - Försöker synka NTP, hoppar över om det tar för lång tid
   - Startar Chromium med kiosk-, touch- och stabilitetsflaggor
6. Skriver Chromium managed policy: `TranslateEnabled=false`

---

## Skärmrotation (RPi Touch Display)

Om bilden visas upp-och-ned, lägg till i `/boot/firmware/config.txt`
under `[all]`:

```ini
lcd_rotate=2
```

`lcd_rotate=2` roterar både skärmbild och pekinmatning 180°.
Starta om efter ändringen.

---

## Byta skärm-URL efteråt

```bash
sudo nano /etc/skarmar/kiosk.env   # ändra SCREEN_URL
sudo reboot
```

Eller kör `install.sh` igen.

---

## Felsökning

**Svart skärm / startar inte:**
```bash
DISPLAY=:0 /usr/local/bin/skarmar-kiosk-launch &
```

**Touch fungerar inte:**
Kontrollera att `--touch-events=enabled` finns i `/usr/local/bin/skarmar-kiosk-launch`.

**Klocka visar fel tid:**
RPi 3B saknar RTC. Tid synkas via NTP vid uppstart. Pi:n behöver nå
routerns inbyggda NTP-server — inte internet.

**Kiosk-fönster kraschar:**
`--disable-dev-shm-usage` är satt för att förhindra krascher på RPi 3B
(1 GB RAM, liten `/dev/shm`).

**Chromium visar translate-bar:**
Policy-filen ska finnas: `cat /etc/chromium/policies/managed/kiosk.json`
Innehåll: `{"TranslateEnabled": false}`
