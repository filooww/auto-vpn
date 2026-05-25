#!/usr/bin/env python3
"""WOW VPN Setup Wizard — PyWebView edition"""
import subprocess, os, sys, json, shutil, threading, time, re

HOME             = os.path.expanduser("~")
VPN_DIR          = os.path.join(HOME, ".vpn")
CONFIG_FILE      = os.path.join(VPN_DIR, "gui_config.json")
WATCHDOG_SH      = os.path.join(VPN_DIR, "watchdog.sh")
LOG_FILE         = os.path.join(VPN_DIR, "vpn.log")
LAUNCHAGENT_WD   = os.path.join(HOME, "Library/LaunchAgents/com.vpn.wow.watchdog.plist")

def run(cmd):
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:" + env.get("PATH", "")
    env.setdefault("HOME", os.path.expanduser("~"))
    env.setdefault("USER", os.getenv("USER", ""))
    env.setdefault("LOGNAME", os.getenv("LOGNAME", ""))
    env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
    env["HOMEBREW_NO_ENV_HINTS"] = "1"
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)

def decode_qr(path):
    """Читаем QR через zbarimg — надёжно работает на macOS"""
    import shutil, tempfile
    try:
        # Копируем в /tmp чтобы избежать проблем с путями
        tmp = "/tmp/wow_qr.jpg"
        shutil.copy2(path, tmp)

        for zbar in ["/opt/homebrew/bin/zbarimg", "/usr/local/bin/zbarimg", "zbarimg"]:
            r = subprocess.run(
                [zbar, "--raw", "-q", tmp],
                capture_output=True, text=True
            )
            if r.returncode == 0 and r.stdout.strip():
                val = r.stdout.strip()
                if val.startswith("otpauth://"):
                    return val
    except Exception as e:
        print("QR error:", e)
    return None

def extract_secret(url):
    m = re.search(r'[?&]secret=([^&]+)', url, re.I)
    return m.group(1).strip() if m else None

def generate_totp(secret):
    for p in ["oathtool","/opt/homebrew/bin/oathtool","/usr/local/bin/oathtool"]:
        r = run(f'{p} --totp --base32 "{secret.strip()}"')
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    try:
        import hmac, hashlib, struct, base64, time as t
        s = secret.strip().upper()
        key = base64.b32decode(s + "=" * ((8 - len(s) % 8) % 8))
        mac = hmac.new(key, struct.pack(">Q", int(t.time())//30), hashlib.sha1).digest()
        offset = mac[-1] & 0xF
        return str(struct.unpack(">I", mac[offset:offset+4])[0] & 0x7FFFFFFF % 1_000_000).zfill(6)
    except: return ""

def write_watchdog(config):
    """Один скрипт делает всё: подключает при старте и следит за VPN"""
    os.makedirs(VPN_DIR, exist_ok=True)
    with open(WATCHDOG_SH, "w") as f:
        f.write(f"""#!/bin/bash
USERNAME="{config['username']}"
SECRET="{config['totp_secret']}"
CONFIG="{config['ovpn_path']}"
LOG="{LOG_FILE}"

cleanup() {{
    # Убиваем все процессы openvpn
    local PIDS=$(pgrep -x openvpn 2>/dev/null)
    local COUNT=$(echo "$PIDS" | grep -c '[0-9]' 2>/dev/null || echo 0)
    if [ "$COUNT" -gt 1 ]; then
        echo "$(date): Найдено $COUNT дублей openvpn — чищу..." >> "$LOG"
        sudo killall openvpn 2>/dev/null
        sleep 2
    elif [ "$COUNT" -eq 1 ]; then
        sudo killall openvpn 2>/dev/null
        sleep 2
    fi
}}

connect() {{
    cleanup
    # Ждём если код почти истёк
    SECONDS_LEFT=$(( 30 - $(date +%S) % 30 ))
    if [ "$SECONDS_LEFT" -lt 5 ]; then
        sleep $(( SECONDS_LEFT + 1 ))
    fi
    CODE=$(/opt/homebrew/bin/oathtool --totp --base32 "$SECRET")
    TMPFILE=$(mktemp)
    echo "$USERNAME" > "$TMPFILE"
    echo "$CODE" >> "$TMPFILE"
    sudo /opt/homebrew/sbin/openvpn \\
      --config "$CONFIG" \\
      --auth-user-pass "$TMPFILE" \\
      --log "$LOG" \\
      --daemon vpn-wow
    rm -f "$TMPFILE"
    echo "$(date): Подключение запущено (код: $CODE)" >> "$LOG"
}}

# Ждём сети при старте системы
sleep 15
connect

# Watchdog: проверяем каждые 30 сек
while true; do
    sleep 30

    # Если больше одного процесса openvpn — дубль, чистим и переподключаем
    VPNCOUNT=$(pgrep -x openvpn 2>/dev/null | grep -c '[0-9]' || echo 0)
    if [ "$VPNCOUNT" -gt 1 ]; then
        echo "$(date): Дублированное подключение ($VPNCOUNT) — перезапускаю..." >> "$LOG"
        connect
        continue
    fi

    # Если нет tun интерфейса с 10.x — VPN упал
    if ! ifconfig 2>/dev/null | grep -q "inet 10\\."; then
        echo "$(date): VPN отвалился — переподключаю..." >> "$LOG"
        connect
    fi
done
""")
    os.chmod(WATCHDOG_SH, 0o755)

def write_launchagent():
    os.makedirs(os.path.dirname(LAUNCHAGENT_WD), exist_ok=True)
    with open(LAUNCHAGENT_WD, "w") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.vpn.wow.watchdog</string>
<key>ProgramArguments</key>
<array><string>/bin/bash</string><string>{WATCHDOG_SH}</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>{LOG_FILE}</string>
<key>StandardErrorPath</key><string>{LOG_FILE}</string>
</dict></plist>""")
    run(f"launchctl unload '{LAUNCHAGENT_WD}' 2>/dev/null")
    run(f"launchctl load '{LAUNCHAGENT_WD}'")

def sudoers_cmd():
    user = os.getenv("USER","user")
    lines = (f"{user} ALL=(ALL) NOPASSWD: /opt/homebrew/sbin/openvpn\\n"
             f"{user} ALL=(ALL) NOPASSWD: /usr/bin/killall\\n")
    return (f"printf '{lines}' | sudo tee /etc/sudoers.d/openvpn > /dev/null "
            f"&& sudo chmod 440 /etc/sudoers.d/openvpn")

# ── HTML UI ──────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{
    --bg:#0d0f14;--card:#141720;--card2:#1a1d26;
    --accent:#4c7cf7;--accent2:#3a6ae8;
    --green:#2ecc8f;--red:#e05c5c;
    --text:#e4e8f4;--sub:#5a6280;--border:#252a3a;
  }
  html,body{width:100%;height:100%;background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:var(--text);overflow:hidden}

  /* ── Splash screen ── */
  #splash{position:fixed;inset:0;background:var(--bg);display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:32px 28px 20px;gap:10px;z-index:100;overflow-y:auto}
  #splash .lock{font-size:52px}
  #splash h1{font-size:22px;font-weight:700;color:#fff}
  #splash .sub{font-size:12px;color:var(--sub)}
  .dep-list{width:320px;margin-top:8px}
  .dep-item{display:flex;align-items:center;gap:10px;padding:6px 0;font-size:12px;color:var(--sub);border-bottom:1px solid var(--border)}
  .dep-item:last-child{border-bottom:none}
  .dep-icon{width:18px;text-align:center;font-size:14px}
  .dep-name{flex:1}
  .dep-status{font-size:11px}
  .dep-status.ok{color:var(--green)}
  .dep-status.installing{color:#f0a030}
  .dep-status.pending{color:var(--sub)}
  .splash-progress{width:320px;height:3px;background:var(--border);border-radius:2px;overflow:hidden;margin-top:12px}
  .splash-fill{height:100%;background:var(--accent);border-radius:2px;width:0;transition:width .5s ease}
  .splash-msg{font-size:11px;color:var(--sub);margin-top:6px}
  .log-box{width:100%;max-width:420px;height:160px;background:#0a0c10;border:1px solid var(--border);border-radius:8px;margin-top:10px;margin-bottom:36px;padding:10px 14px;overflow-y:auto;font-family:"SF Mono",Monaco,"Cascadia Code",monospace;font-size:10px;line-height:1.7;text-align:left;box-sizing:border-box}
  .log-box .log-ok{color:#2ecc8f}
  .log-box .log-err{color:#f87171}
  .log-box .log-warn{color:#f0a030}
  .log-box .log-info{color:#6b9ef7}
  .log-box .log-dim{color:#3a4055}
  .log-box .log-white{color:#c8cde0}
  .log-cursor{display:inline-block;width:6px;height:11px;background:#4c7cf7;animation:blink .8s step-end infinite;vertical-align:middle;margin-left:2px}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:0}}

  /* ── Main UI ── */
  #main{display:none;flex-direction:column;padding:28px 28px 20px;height:100%}
  .header{display:flex;align-items:center;gap:14px;margin-bottom:20px}
  .lock-sm{font-size:28px;line-height:1}
  .header-text h1{font-size:20px;font-weight:700;color:#fff;letter-spacing:-0.3px}
  .header-text p{font-size:12px;color:var(--sub);margin-top:2px}
  .divider{height:1px;background:var(--border);margin-bottom:16px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:10px;margin-bottom:10px;overflow:hidden}
  .card-top{display:flex;align-items:center;gap:10px;padding:12px 14px 8px}
  .badge{background:var(--accent);color:#fff;font-size:10px;font-weight:700;width:20px;height:20px;border-radius:5px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
  .card-title{font-size:13px;font-weight:600;flex:1}
  .pick-btn{background:#1f2436;color:var(--accent);border:none;border-radius:6px;padding:5px 12px;font-size:11px;font-family:inherit;cursor:pointer;transition:background .15s}
  .pick-btn:hover{background:#252b40}
  .card-status{background:var(--card2);margin:0 14px 12px;border-radius:6px;padding:7px 10px;font-size:11px;color:var(--sub);min-height:30px;display:flex;align-items:center}
  .card-status.ok{color:var(--green)}
  .card-status.err{color:var(--red)}
  .login-row{display:flex;align-items:center;gap:10px;padding:12px 14px}
  .login-row label{font-size:13px;font-weight:600;flex-shrink:0}
  .login-row input{flex:1;background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:7px 10px;font-size:13px;font-family:inherit;color:var(--text);outline:none;transition:border-color .15s}
  .login-row input:focus{border-color:var(--accent)}
  .status-bar{font-size:11px;color:var(--sub);text-align:center;margin:8px 0 4px;min-height:16px}
  .status-bar.ok{color:var(--green)}
  .status-bar.err{color:var(--red)}
  .status-bar.info{color:#a0b0d0}
  .progress-track{height:3px;background:var(--border);border-radius:2px;margin-bottom:12px;overflow:hidden}
  .progress-fill{height:100%;background:var(--accent);border-radius:2px;width:0;transition:width .4s ease}
  .install-btn{width:100%;padding:13px;background:var(--accent);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:background .15s}
  .install-btn:hover{background:var(--accent2)}
  .install-btn:disabled{background:#2a2f42;color:#4a5068;cursor:not-allowed}
</style>
</head>
<body>

<!-- Splash: установка зависимостей -->
<div id="splash">
  <div class="lock">🔒</div>
  <h1>WOW VPN</h1>
  <div class="sub">Preparing dependencies...</div>
  <div class="dep-list">
    <div class="dep-item" id="dep-brew">
      <span class="dep-icon">🍺</span>
      <span class="dep-name">Homebrew</span>
      <span class="dep-status pending" id="dep-brew-s">waiting...</span>
    </div>
    <div class="dep-item" id="dep-openvpn">
      <span class="dep-icon">🔐</span>
      <span class="dep-name">OpenVPN</span>
      <span class="dep-status pending" id="dep-openvpn-s">waiting...</span>
    </div>
    <div class="dep-item" id="dep-oath">
      <span class="dep-icon">🔑</span>
      <span class="dep-name">oath-toolkit</span>
      <span class="dep-status pending" id="dep-oath-s">waiting...</span>
    </div>
    <div class="dep-item" id="dep-zbar">
      <span class="dep-icon">📷</span>
      <span class="dep-name">zbar (QR reader)</span>
      <span class="dep-status pending" id="dep-zbar-s">waiting...</span>
    </div>
    <div class="dep-item" id="dep-pywebview">
      <span class="dep-icon">🐍</span>
      <span class="dep-name">pywebview</span>
      <span class="dep-status pending" id="dep-pywebview-s">waiting...</span>
    </div>
  </div>
  <div class="splash-progress"><div class="splash-fill" id="splash-fill"></div></div>
  <div class="splash-msg" id="splash-msg">Checking dependencies...</div>
  <div class="log-box" id="log-box"><span class="log-dim">$ </span><span class="log-info">WOW VPN Setup starting...</span><span class="log-cursor"></span></div>
</div>

<!-- Main UI -->
<div id="main">
  <div class="header">
    <div class="lock-sm">🔒</div>
    <div class="header-text">
      <h1>WOW VPN</h1>
      <p>One-time setup · ~30 seconds</p>
    </div>
  </div>
  <div class="divider"></div>
  <div class="card">
    <div class="card-top">
      <div class="badge">1</div>
      <span class="card-title">📄 VPN config file</span>
      <button class="pick-btn" onclick="pickOvpn()">Select .ovpn</button>
    </div>
    <div class="card-status" id="s1">No file selected</div>
  </div>
  <div class="card">
    <div class="card-top">
      <div class="badge">2</div>
      <span class="card-title">📷 QR code screenshot</span>
      <button class="pick-btn" onclick="pickQr()">Select photo</button>
    </div>
    <div class="card-status" id="s2">No photo selected</div>
  </div>
  <div class="card">
    <div class="login-row">
      <div class="badge">3</div>
      <label>Login:</label>
      <input type="text" id="login" placeholder="Enter login">
    </div>
  </div>
  <div class="status-bar" id="status">Select files and click Install</div>
  <div class="progress-track"><div class="progress-fill" id="progress"></div></div>
  <button class="install-btn" id="installBtn" onclick="startInstall()">Install</button>
</div>

<script>
function pickOvpn()  { pywebview.api.pick_ovpn() }
function pickQr()    { pywebview.api.pick_qr() }
function startInstall() {
  const login = document.getElementById('login').value.trim()
  if (!login) { setStatus('Enter login', 'err'); return }
  pywebview.api.install(login)
}
function setStatus(msg, cls='') {
  const el = document.getElementById('status')
  el.textContent = msg; el.className = 'status-bar ' + cls
}
function setProgress(pct) {
  document.getElementById('progress').style.width = pct + '%'
}
function setCard(id, text, cls='') {
  const el = document.getElementById(id)
  el.textContent = text; el.className = 'card-status ' + cls
}
function addLog(msg, cls='log-white') {
  const box = document.getElementById('log-box')
  // Remove cursor from last line
  const cursors = box.querySelectorAll('.log-cursor')
  cursors.forEach(c => c.remove())
  // Add new line
  const line = document.createElement('div')
  line.innerHTML = '<span class="log-dim">$ </span><span class="' + cls + '">' + msg + '</span><span class="log-cursor"></span>'
  box.appendChild(line)
  box.scrollTop = box.scrollHeight
}
function setDep(id, status, cls) {
  const el = document.getElementById('dep-' + id + '-s')
  el.textContent = status; el.className = 'dep-status ' + cls
}
function setSplashProgress(pct) {
  document.getElementById('splash-fill').style.width = pct + '%'
}
function setSplashMsg(msg) {
  document.getElementById('splash-msg').textContent = msg
}
function showMain() {
  document.getElementById('splash').style.display = 'none'
  document.getElementById('main').style.display = 'flex'
}
</script>
</body>
</html>"""

class Api:
    def __init__(self):
        self.window      = None
        self.ovpn_path   = ""
        self.totp_secret = ""

    def _js(self, code):
        if self.window:
            self.window.evaluate_js(code)

    def check_and_install_deps(self):
        """Вызывается при старте — проверяет и устанавливает зависимости"""
        threading.Thread(target=self._do_deps, daemon=True).start()

    def _log(self, msg, cls="log-white"):
        import json
        self._js(f"addLog({json.dumps(msg)},{json.dumps(cls)})")

    def _do_deps(self):
        deps = [
            ("brew",      self._check_brew,      self._install_brew,      "Homebrew"),
            ("openvpn",   self._check_openvpn,   self._install_openvpn,   "openvpn"),
            ("oath",      self._check_oath,       self._install_oath,      "oath-toolkit"),
            ("zbar",      self._check_zbar,       self._install_zbar,      "zbar"),
            ("pywebview", self._check_pywebview,  self._install_pywebview, "pywebview"),
        ]
        total = len(deps)
        failed = []
        self._log("Checking dependencies...", "log-info")

        for i, (name, check, install, label) in enumerate(deps):
            pct = int((i / total) * 90)
            self._js(f"setSplashProgress({pct})")
            if check():
                self._js(f"setDep('{name}','✓ ready','ok')")
                self._log(f"✓ {label} — already installed", "log-ok")
            else:
                self._js(f"setDep('{name}','installing...','installing')")
                self._js(f"setSplashMsg('Installing {label}...')")
                self._log(f"→ Installing {label}...", "log-warn")
                install()
                time.sleep(1)
                if check():
                    self._js(f"setDep('{name}','✓ installed','ok')")
                    self._log(f"✓ {label} — installed successfully", "log-ok")
                else:
                    self._js(f"setDep('{name}','✗ failed','installing')")
                    self._log(f"✗ {label} — failed to install", "log-err")
                    failed.append(label)

        self._js("setSplashProgress(100)")
        if failed:
            self._log(f"✗ Failed: {', '.join(failed)}", "log-err")
            self._js(f"setSplashMsg('Some deps failed — install via brew and retry')")
            time.sleep(3)
        else:
            self._log("✓ All dependencies ready!", "log-ok")
            self._js("setSplashMsg('All ready!')")
            time.sleep(0.8)
        self._js("showMain()")

    def _check_brew(self):
        return (os.path.exists("/opt/homebrew/bin/brew") or
                os.path.exists("/usr/local/bin/brew") or
                run("command -v brew").returncode == 0)

    def _brew(self, pkg):
        """Install brew package — force ARM64 to avoid Rosetta issue"""
        brew = ("/opt/homebrew/bin/brew" if os.path.exists("/opt/homebrew/bin/brew")
                else "/usr/local/bin/brew")
        r = run(f"arch -arm64 {brew} install {pkg}")
        # Show brew output in log
        for line in (r.stdout + r.stderr).splitlines():
            line = line.strip()
            if not line:
                continue
            if "🍺" in line or "installed" in line.lower():
                self._log(line, "log-ok")
            elif "Error" in line or "error" in line:
                self._log(line, "log-err")
            elif "==>" in line or "Pouring" in line or "Fetching" in line:
                self._log(line, "log-info")
            elif line:
                self._log(line, "log-dim")

    def _install_brew(self):
        run('arch -arm64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')

    def _check_openvpn(self):
        r = run("/opt/homebrew/sbin/openvpn --version 2>/dev/null || /usr/local/sbin/openvpn --version 2>/dev/null")
        return r.returncode == 0

    def _install_openvpn(self):
        self._brew("openvpn")

    def _check_oath(self):
        r = run("/opt/homebrew/bin/oathtool --version 2>/dev/null || /usr/local/bin/oathtool --version 2>/dev/null")
        return r.returncode == 0

    def _install_oath(self):
        self._brew("oath-toolkit")

    def _check_zbar(self):
        r = run("/opt/homebrew/bin/zbarimg --version 2>/dev/null || /usr/local/bin/zbarimg --version 2>/dev/null")
        return r.returncode == 0

    def _install_zbar(self):
        self._brew("zbar")

    def _check_pywebview(self):
        try:
            import webview
            return True
        except ImportError:
            return False

    def _install_pywebview(self):
        subprocess.run([sys.executable, "-m", "pip", "install", "pywebview",
                        "--break-system-packages"], capture_output=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "pywebview",
                        "--user"], capture_output=True)

    def pick_ovpn(self):
        import webview
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("OpenVPN Config (*.ovpn)", "All files (*.*)")
        )
        if paths:
            self.ovpn_path = paths[0]
            name = os.path.basename(paths[0])
            self._js(f"setCard('s1','✓  {name}','ok')")
            login = os.path.splitext(name)[0]
            self._js(f"document.getElementById('login').value='{login}'")

    def pick_qr(self):
        import webview, urllib.parse
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Images (*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp)", "All files (*.*)")
        )
        if paths:
            self._js("setCard('s2','🔍 Читаю QR-код...','')")
            def worker():
                raw = paths[0]
                # Убираем file:// префикс
                if raw.startswith("file://"):
                    raw = urllib.parse.unquote(raw[7:])
                # Копируем в /tmp с простым именем (обход sandbox и спецсимволов)
                import shutil, tempfile
                tmp = "/tmp/wow_qr_scan.jpg"
                try:
                    shutil.copy2(raw, tmp)
                    actual_path = tmp
                except:
                    actual_path = raw
                url = decode_qr(actual_path)
                if url:
                    secret = extract_secret(url)
                    if secret:
                        self.totp_secret = secret
                        code = generate_totp(secret)
                        name = os.path.basename(paths[0])
                        msg = f"✓  {name}   (код: {code})" if code else "✓  Секрет извлечён"
                        self._js(f"setCard('s2',{json.dumps(msg)},'ok')")
                    else:
                        self._js("setCard('s2','⚠️ QR прочитан, секрет не найден','err')")
                else:
                    self._js("setCard('s2','❌ Не удалось прочитать QR','err')")
            threading.Thread(target=worker, daemon=True).start()

    def install(self, login):
        if not self.ovpn_path or not os.path.exists(self.ovpn_path):
            self._js("setStatus('❌ Выбери .ovpn файл','err')"); return
        if not self.totp_secret:
            self._js("setStatus('❌ QR-код не прочитан','err')"); return
        self._js("document.getElementById('installBtn').disabled=true")
        threading.Thread(target=self._do_install, args=(login,), daemon=True).start()

    def _do_install(self, login):
        def s(pct, msg, cls="info"):
            self._js(f"setStatus({json.dumps(msg)},{json.dumps(cls)})")
            self._js(f"setProgress({pct})")
            time.sleep(0.35)
        try:
            s(8,  "📁 Создаю ~/.vpn...")
            os.makedirs(VPN_DIR, exist_ok=True)

            s(20, "📦 Проверяю oath-toolkit...")
            if run("which oathtool || which /opt/homebrew/bin/oathtool").returncode != 0:
                s(22, "📦 Устанавливаю oath-toolkit..."); run("brew install oath-toolkit")

            s(35, "📦 Проверяю openvpn...")
            if run("test -f /opt/homebrew/sbin/openvpn").returncode != 0:
                s(37, "📦 Устанавливаю openvpn..."); run("brew install openvpn")

            s(50, "📄 Копирую .ovpn...")
            dest = os.path.join(VPN_DIR, os.path.basename(self.ovpn_path))
            if self.ovpn_path != dest: shutil.copy2(self.ovpn_path, dest)

            config = {"ovpn_path": dest, "totp_secret": self.totp_secret, "username": login}

            s(62, "🔧 Пишу watchdog скрипт...")
            write_watchdog(config)

            s(75, "🔐 Настраиваю sudo (нужен пароль)...")
            cmd = sudoers_cmd().replace('"', '\\"').replace("'", "'\\''")
            run(f"osascript -e 'do shell script \"{cmd}\" with administrator privileges'")

            s(88, "🚀 Добавляю в автозапуск...")
            write_launchagent()

            s(95, "💾 Сохраняю конфиг...")
            with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=2)

            s(100, "✅ Готово! Подключаюсь к VPN...", "ok")
            time.sleep(1)
            # Запускаем watchdog и сразу выходим
            subprocess.Popen(
                ["bash", WATCHDOG_SH],
                close_fds=True,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Удаляем .app и архив рядом с ним
            macos_dir = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.dirname(os.path.dirname(macos_dir))
            parent_dir = os.path.dirname(app_path)
            app_name = os.path.basename(app_path)
            zip_name = app_name.replace(".app", "")
            # Удаляем .app + любой .zip рядом с похожим именем
            cleanup = (
                f'sleep 2 && '
                f'rm -rf "{app_path}" && '
                f'rm -f "{parent_dir}/WOW_VPN_Setup.zip" '
                f'"{parent_dir}/WOW VPN Setup.zip" '
                f'"{parent_dir}/{zip_name}.zip"'
            )
            subprocess.Popen(
                cleanup,
                shell=True, close_fds=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            os._exit(0)

        except Exception as e:
            self._js(f"setStatus('❌ Ошибка: {e}','err')")
            self._js("document.getElementById('installBtn').disabled=false")

    def _goodbye(self):
        self_path = os.path.abspath(__file__)
        subprocess.Popen(
            f'sleep 2 && rm -f "{self_path}"',
            shell=True, close_fds=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # Закрываем через главный поток
        if self.window:
            self.window.destroy()
        # Принудительно через 1 сек если не закрылось
        def force_exit():
            time.sleep(1)
            os._exit(0)
        threading.Thread(target=force_exit, daemon=True).start()

if __name__ == "__main__":
    try:
        import webview
    except ImportError:
        subprocess.run([sys.executable,"-m","pip","install","pywebview","--break-system-packages"], capture_output=True)
        subprocess.run([sys.executable,"-m","pip","install","pywebview","--user"], capture_output=True)
        import webview

    api = Api()
    window = webview.create_window(
        "WOW VPN — Быстрая настройка",
        html=HTML, js_api=api,
        width=480, height=600,
        resizable=False,
        background_color="#0d0f14",
    )
    api.window = window
    webview.start(func=api.check_and_install_deps)
    os._exit(0)
