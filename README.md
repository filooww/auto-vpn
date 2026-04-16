# OpenVPN Connect 2FA Automation for macOS

This project allows you to fully automate connecting to your VPN every time you open your MacBook lid.

---

## 🛠 Step 1: Installing Tools (via Terminal)

Open the Terminal and install the package manager and required utilities.

### Install Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Install utilities for 2FA and QR code scanning
```bash
brew install oath-toolkit zbar git
```

---

## 🔑 Step 2: Extracting the Secret from the QR Code

Use the QR code that was sent to you (e.g., in Telegram) when setting up your VPN.

```bash
zbarimg ~/YOUR_PATH/qr.png
```

Copy the value that appears after `secret=` (for example: `6APTQGIS...`).  
You’ll need this value to configure the script.

---

## 📂 Step 3: Cloning the Repository and Configuration

Now let’s download the repository.

### Go to Desktop
```bash
cd ~/Desktop
```

### Clone the repository
```bash
git clone https://github.com/filooww/auto-vpn.git vpn-auto
```

### Enter the folder
```bash
cd vpn-auto
```

### Configure your secret
Open the `vpn_auto.scpt` file in **Script Editor** and replace `YOUR_SECRET`  
with the value obtained in Step 2. Save your changes.

---

## ⏳ Step 4: Setting Up Hammerspoon

Install Hammerspoon:
```bash
brew install --cask hammerspoon
```

Open the Hammerspoon configuration (click the hammer icon in your menu bar → **Open Config**)  
and paste the following code to run the script automatically:

```lua
function runVPN()
    local scriptPath = os.getenv("HOME") .. "/Desktop/vpn_auto/vpn_auto.scpt"

    hs.notify.new({title="VPN Automation", informativeText="System woke up. Connecting..."}):send()
    hs.execute("osascript " .. scriptPath)
end

watcher = hs.caffeinate.watcher.new(function(event)
    if (event == hs.caffeinate.watcher.systemDidWake) then
        hs.timer.doAfter(0.5, runVPN)
    end
end)

watcher:start()
```

Click **Save** and then **Reload Config** in the Hammerspoon menu.  
You can adjust the delay time (`0.5` seconds) as needed.

---

## 🛡 Step 5: Granting Permissions

Make sure to give Hammerspoon the required accessibility permissions:

> **System Settings → Privacy & Security → Accessibility**

---

## ✅ Done!

After setup, your Mac will automatically connect to the VPN as soon as it wakes from sleep.

---

### 🧠 Tip
If you keep the script on a different path, update the `scriptPath` variable in Hammerspoon accordingly.

---
