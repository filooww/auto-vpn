# 🔒 Auto VPN

Automatic corporate VPN connection for macOS. Connects on every login, reconnects if dropped.

---

## Install

1. Download `WOW.VPN.Setup.dmg` from [Releases](https://github.com/filooww/auto-vpn/releases/latest)
2. Open the DMG and drag **WOW VPN Setup** to **Applications**
3. Open the app from Applications
4. Fill in 3 fields and click **Install**

Done — VPN will connect automatically on every login.

---

## What you need

| | |
|---|---|
| 📄 `.ovpn` file | VPN config from your IT department |
| 📷 QR code | Screenshot from your authenticator app |
| 👤 Login | Usually the `.ovpn` filename without extension |

---

## Requirements

- macOS 11+ (Apple Silicon)
- [Homebrew](https://brew.sh) — installed automatically if missing

---

## Commands

```bash
# Disconnect VPN
sudo killall openvpn

# Check status
ifconfig | grep "inet 10\."

# View log
tail -30 ~/.vpn/vpn.log
```

---

## Uninstall

```bash
sudo killall openvpn 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.vpn.wow.watchdog.plist 2>/dev/null
rm -f ~/Library/LaunchAgents/com.vpn.wow*.plist
rm -rf ~/.vpn
sudo rm -f /etc/sudoers.d/openvpn
```
