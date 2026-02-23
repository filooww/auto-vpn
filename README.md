# Автоматизация OpenVPN Connect 2FA для macOS

Этот проект автоматизирует ввод 2FA-кода в OpenVPN Connect при пробуждении Mac.

## 🛠 Шаг 1: Установка инструментов (Терминал)

1. **Установите Homebrew** (менеджер пакетов):
   ```bash
   /bin/bash -c "$(curl -fsSL [https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh](https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh))"

    Установите утилиты:
    Bash

    brew install oath-toolkit zbar

🔑 Шаг 2: Получение секрета из QR-кода

    Сделай скриншот QR-кода и сохрани на рабочий стол как qr.png.

    В Терминале выполни: zbarimg ~/Desktop/qr.png.

    Скопируй текст после secret=.

    Проверь генерацию цифр:
    Bash

    /opt/homebrew/bin/oathtool --totp -b ВАШ_СЕКРЕТ

📝 Шаг 3: AppleScript (vpn_auto.scpt)

Создай в Редакторе скриптов и сохрани на Рабочий стол как vpn_auto.scpt:
AppleScript

-- Генерируем код
set myCode to do shell script "/opt/homebrew/bin/oathtool --totp -b ВАШ_СЕКРЕТ"
set the clipboard to myCode

tell application "OpenVPN Connect" to activate
delay 1

tell application "System Events"
    tell process "OpenVPN Connect"
        key code 36 -- Закрыть ошибку (OK)
        delay 1
        key code 36 -- Нажать Connect
        delay 2
        keystroke "v" using {command down} -- Вставить код
        delay 0.5
        key code 36 -- Подтвердить
    end tell
end tell

⏳ Шаг 4: Hammerspoon (init.lua)

Вставь в конфиг Hammerspoon (Open Config):
Lua

function runVPN()
    -- Автоматически подставляет имя твоего пользователя
    local scriptPath = "/Users/" .. os.getenv("USER") .. "/Desktop/vpn_auto.scpt"
    hs.execute("osascript " .. scriptPath)
end

watcher = hs.caffeinate.watcher.new(function(event)
    if (event == hs.caffeinate.watcher.systemDidWake) then
        hs.timer.doAfter(6, runVPN) -- Ждем 6 сек (стабилизация Wi-Fi)
    end
end)
watcher:start()

🛡 Шаг 5: Права доступа

Дай разрешение Hammerspoon в:
Системные настройки -> Конфиденциальность -> Универсальный доступ.
