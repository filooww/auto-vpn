OpenVPN Connect 2FA Automation for macOS

This project allows you to fully automate VPN connection each time you open your laptop lid.

🛠 Step 1: Installing tools (via Terminal)

Open the Terminal and install the package manager and required utilities:

— Install Homebrew

bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

— Install utilities for 2FA and QR code scanning

bash
brew install oath-toolkit zbar git

🔑 Step 2: Extracting the secret from the QR code

Use the QR code that was sent to you (e.g., in Telegram) when setting up the VPN.

bash
zbarimg ~/YOUR_PATH/qr.png

Copy the value that appears after secret= (for example: 6APTQGIS...). You’ll need it later when setting up the script.

📂 Step 3: Cloning the repository and configuration

Now let’s download the repository:

— Go to Desktop

bash
cd ~/Desktop

— Clone the repository

bash
git clone https://github.com/fastonyou/auto-vpn.git vpn-auto

— Enter the folder

bash
cd vpn-auto

Configure your secret:

Open the file vpn_auto.scpt in Script Editor and replace YOUR_SECRET with the value you obtained in Step 2. Save the changes.

⏳ Step 4: Setting up Hammerspoon

Install Hammerspoon:

bash
brew install --cask hammerspoon

Open the Hammerspoon config (click the hammer icon in your menu bar → Open Config), and insert the following code to run the script from your cloned folder:

lua
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

Click Save and then Reload Config in the Hammerspoon menu.
You can change the delay value in the script if needed.

🛡 Step 5: Granting permissions

Make sure to grant Hammerspoon the necessary accessibility permissions:
System Settings → Privacy & Security → Accessibility
