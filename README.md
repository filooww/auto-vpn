<div align="center">

<img src="https://raw.githubusercontent.com/filooww/auto-vpn/main/banner.svg" width="680"/>

[![Release](https://img.shields.io/github/v/release/filooww/auto-vpn?color=4c7cf7&style=flat-square)](https://github.com/filooww/auto-vpn/releases/latest)
[![Platform](https://img.shields.io/badge/platform-macOS%2011%2B-lightgrey?style=flat-square)](https://github.com/filooww/auto-vpn)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

</div>

---

## What it does

---

## What it does

Auto VPN sets up a silent background process that:

- 🔐 **Generates TOTP codes automatically** from your QR authenticator secret
- 🚀 **Connects on every login** via macOS LaunchAgent — no manual action needed
- 👁️ **Watches the connection** every 30 seconds and reconnects if it drops
- 🧹 **Cleans up duplicates** — kills stale OpenVPN processes automatically
- ⏱️ **Smart TOTP timing** — waits for a fresh code if the current one is about to expire
- 📦 **Installs all dependencies** — Homebrew packages installed automatically on first run

---

## Quick Start

1. **Download** `WOW.VPN.Setup.dmg` from [Releases](https://github.com/filooww/auto-vpn/releases/latest)
2. **Open** the DMG and drag **WOW VPN Setup** → **Applications**
3. **Launch** the app from Applications
4. **Fill in 3 fields** and click Install:

| Field | What to provide |
|-------|----------------|
| 📄 `.ovpn` file | VPN config file from your IT department |
| 📷 QR code | Screenshot or photo of your authenticator QR code |
| 👤 Login | Your VPN username (usually the `.ovpn` filename without extension) |

5. **Done.** The app installs everything, starts the VPN, and deletes itself.

---

## How it works

```
System Login
    │
    └─▶ LaunchAgent → watchdog.sh
              │
              ├─ Wait 15s for network
              ├─ Check TOTP timing (wait if < 5s left)
              ├─ Generate 6-digit code via oathtool
              ├─ Connect OpenVPN in background (--daemon)
              │
              └─ Loop every 30s
                    ├─ Duplicate processes? → kill & reconnect
                    └─ No tun interface (10.x.x.x)? → reconnect
```

---

## Requirements

| | |
|--|--|
| macOS | 11.0+ (Apple Silicon) |
| Homebrew | [brew.sh](https://brew.sh) — installed automatically if missing |
| OpenVPN | Installed automatically |
| oath-toolkit | Installed automatically |
| zbar | Installed automatically |

---

## Files created

```
~/.vpn/
├── watchdog.sh          # Main script — connects and monitors
├── your_config.ovpn     # VPN config (copied during setup)
├── gui_config.json      # Settings (username, secret, ovpn path)
└── vpn.log              # Connection log

~/Library/LaunchAgents/
└── com.vpn.wow.watchdog.plist  # Starts watchdog on login
```

---

## Useful commands

```bash
# Check if connected
ifconfig | grep "inet 10\."

# View connection log
tail -30 ~/.vpn/vpn.log

# Disconnect
sudo killall openvpn

# Check watchdog status
launchctl list | grep vpn

# Generate TOTP code manually
oathtool --totp --base32 "YOUR_SECRET"
```

---

## Uninstall

```bash
sudo killall openvpn 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.vpn.wow.watchdog.plist 2>/dev/null
rm -f ~/Library/LaunchAgents/com.vpn.wow*.plist
rm -rf ~/.vpn
sudo rm -f /etc/sudoers.d/openvpn
echo "Removed"
```

---

## Security

- Your TOTP secret is stored locally in `~/.vpn/gui_config.json`, readable only by your user account
- The setup app requests admin privileges only to configure passwordless `sudo` for OpenVPN
- No data is sent anywhere — everything runs locally

---

## License

MIT
