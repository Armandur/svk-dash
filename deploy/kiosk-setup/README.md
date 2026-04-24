# skarmar – Pi-kiosk bootstrap

Testat på **Raspberry Pi 3B** med officiell **RPi Touch Display** och
**Raspberry Pi OS Bookworm Desktop** (X11, inte Wayland).

---

## Steg 1 – Flasha OS

Använd **Raspberry Pi Imager** och välj:
- **OS:** Raspberry Pi OS (32-bit) – Bookworm Desktop
- **Lagring:** ditt SD-kort

Klicka på kugghjulet och konfigurera:
- Hostname (t.ex. `kiosk-kyrkan`)
- Aktivera SSH
- Användare: `pi` + lösenord
- Wifi om du inte använder ethernet (Ethernet rekommenderas)

---

## Steg 2 – Skapa en skärm i admin

Gå till `http://192.168.1.42:8000/admin/screens` och skapa en ny skärm.
Notera slugen (t.ex. `kyrkan`). URL:en du ska använda är:

```
http://192.168.1.42:8000/s/kyrkan
```

---

## Steg 3 – Installera kiosk

SSH:a in till Pi:n och kör:

```bash
curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash
# — eller kopiera filen manuellt och kör:
bash install.sh
```

Scriptet frågar efter `SCREEN_URL`. Ange t.ex.:
```
http://192.168.1.42:8000/s/kyrkan
```

Sedan:
```bash
sudo reboot
```

---

## Vad scriptet gör

1. Sparar `SCREEN_URL` i `/etc/skarmar/kiosk.env`
2. Stänger av Wayland (tvingar X11)
3. Aktiverar autologin till skrivbordet
4. Installerar `chromium-browser` och `unclutter` vid behov
5. Skriver `~/.config/lxsession/LXDE-pi/autostart`
6. Skriver `/usr/local/bin/skarmar-kiosk-launch` som:
   - Väntar på att servern (`192.168.1.42`) svarar på ping (max 60s)
   - Försöker synka NTP men hoppar över om det tar för lång tid
   - Startar Chromium i kiosk-läge med touch- och stabilitetsflaggor

---

## Skärmrotation (RPi Touch Display)

Om bilden visas upp-och-ned, lägg till i `/boot/firmware/config.txt`
under `[all]`:

```ini
lcd_rotate=2
```

`lcd_rotate=2` roterar både skärmbild och pekinmatning 180°.
Starta om efter ändringen.

För 90°/270°-rotation (stående läge):
```ini
display_rotate=1   # 90° medurs
display_rotate=3   # 270° medurs (= 90° moturs)
```
Obs: `display_rotate` roterar inte pekinmatning automatiskt — kontakta
mig om du behöver det.

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
# Testa manuellt utan kiosk-läge:
source /etc/skarmar/kiosk.env
chromium-browser "$SCREEN_URL"
```

**Touch fungerar inte:**
Kontrollera att `--touch-events=enabled` finns i `/usr/local/bin/skarmar-kiosk-launch`.

**Klocka visar fel tid:**
RPi 3B saknar RTC. Tid synkas via NTP när nätverket är uppe.
Servern på `192.168.1.42` behöver inte ha internet — men Pi:n behöver
nå en NTP-server (t.ex. routerns inbyggda) för korrekt tid.

**Kiosk-fönster stängs / kraschar:**
Chromium-flaggan `--disable-dev-shm-usage` är satt för att förhindra
krascher på RPi 3B (1 GB RAM, liten `/dev/shm`).
