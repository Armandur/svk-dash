# skarmar – Pi-kiosk bootstrap

Kör på en **Raspberry Pi OS Bookworm Desktop**-installation (X11, inte Wayland).

## Krav

- Raspberry Pi OS Bookworm Desktop (64-bit eller 32-bit)
- Aktiv internetanslutning under installationen
- Pi:n inloggad som standardanvändaren `pi` (eller annan sudoer)

## Installation

```bash
bash install.sh
sudo reboot
```

Scriptet frågar efter `SCREEN_URL` (t.ex. `https://skarmar.svky.se/s/kyrkan`) och sparar
den i `/etc/skarmar/kiosk.env`. Kör scriptet igen för att byta skärm.

## Vad scriptet gör

1. Sparar `SCREEN_URL` i `/etc/skarmar/kiosk.env`
2. Stänger av Wayland i lightdm (tvingar X11)
3. Aktiverar autologin till skrivbordet
4. Installerar `chromium-browser` och `unclutter` om de saknas
5. Skriver `~/.config/lxsession/LXDE-pi/autostart` med skärmsläckarspärr och kiosk-start
6. Skriver `/usr/local/bin/skarmar-kiosk-launch` som väntar på nät + NTP innan Chromium startas

## Byta skärm-URL efteråt

```bash
sudo nano /etc/skarmar/kiosk.env   # ändra SCREEN_URL
sudo reboot
```

Eller kör `install.sh` igen.
