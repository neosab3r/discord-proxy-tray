# Discord Proxy Tray

Трей-приложение для desktop Discord на Windows: **TCP → локальный SOCKS** и **UDP голос/стримы → DPI desync**, без системного TUN на весь ПК.

[English](README.en.md)

Репозиторий: https://github.com/neosab3r/discord-proxy-tray

---

## Возможности

- Раздельные тумблеры **TCP proxy** и **Stream desync**
- Установка `DWrite.dll` + `force-proxy.dll` в Discord `app-*` и поддержка после обновлений клиента
- Мягкое выключение TCP через `PROXY_ENABLED` (DLL остаются на диске)
- Автозапуск через Task Scheduler (вход в систему, права администратора) с отложенным восстановлением режимов
- Пресеты desync: папка `presets/` в репо + синхронизация с GitHub, локальный «последний рабочий»
- Status, toast при критичных/предупреждающих событиях, логи в `data/logs/`
- Portable: состояние в `data/`, бинарники в `vendor/`

---

## Как это работает

```text
Discord.exe
  ├─ TCP  → DWrite.dll → force-proxy.dll → 127.0.0.1:10808 → v2rayN / Happ → VPN
  └─ UDP  → напрямую + winws (WinDivert desync) → Discord media
```

Чат, API, CDN и загрузки — в основном **TCP**. Голос, Go Live и WebRTC — в основном **UDP**.  
Проект — гибрид: SOCKS для TCP, zapret/winws desync для UDP, а не «весь Discord в TUN».

Используемый `force-proxy` — **только TCP**, чтобы UDP оставался для winws.

---

## Требования

1. Windows 10/11; tray лучше запускать **от администратора** (WinDivert).
2. VPN-клиент с **локальным SOCKS** (по умолчанию `127.0.0.1:10808`), **TUN выключен**, system proxy Clear:
   - **v2rayN** — inbound SOCKS/mixed
   - **Happ** — Start + локальный proxy
3. Desktop Discord.

Бинарники sidecar уже лежат в `vendor/` (см. [licenses/NOTICE.md](licenses/NOTICE.md)).

---

## Быстрый старт

```powershell
cd discord-proxy-tray
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
# Желательно elevated PowerShell:
python -m discord_proxy_tray
```

Включите **TCP proxy**, после первой установки DLL один раз перезапустите Discord.  
Для голоса/стримов включите **Stream desync** и при необходимости смените пресет.

---

## Режимы

| TCP | Stream | Типичный результат |
|-----|--------|--------------------|
| ON | ON | Чат + голос/стримы (рекомендуется) |
| ON | OFF | Чат ок; guild voice часто «Не установлен маршрут» |
| OFF | ON | Только desync; TCP может оставаться заблокированным |
| OFF | OFF | Soft-off TCP (`PROXY_ENABLED=0`) + останов winws |

Иконка: зелёная — оба, синяя — только TCP, жёлтая — только desync, красная — выкл.

Не совмещайте гибрид с **TUN** у VPN-клиента — ломается схема DLL + winws.

---

## Пресеты

| Слой | Где |
|------|-----|
| Репозиторий / CI | `presets/` — источник правды, Action обновляет раз в день |
| Кэш приложения | `data/presets/remote/` — скачивается с GitHub, если `version.txt` новее |
| Ваши | `data/presets/local/` — last working и ручные копии |

Порядок выбора: **local → remote → `presets/` рядом с приложением**.  
Папка `presets/` в клоне/релизе — только offline-fallback; обновлять её вручную при каждом релизе не нужно: клиент подтягивает новую версию с GitHub сам.

URL по умолчанию: `…/master/presets`. CI: `.github/workflows/update-presets.yml` из [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).

---

## Архитектура

```text
Tray (Python)
  ├─ установка force-proxy / soft PROXY_ENABLED + watcher Discord app-*
  └─ процесс winws + аргументы пресета + WinDivert
```

Конфиг и логи рантайма: `data/`.  
Sidecar: `vendor/DWrite.dll`, `vendor/force-proxy.dll`, `vendor/zapret/`.

---

## Стек

| Слой | Технологии |
|------|------------|
| Приложение | Python 3.11+, pystray, Pillow, customtkinter, httpx, psutil |
| TCP | discord-voice-proxy `DWrite.dll` + force-proxy-tcp-only |
| UDP | winws + WinDivert (сборка Flowseal / bol-van zapret) |

Tray не собирает эти DLL сам — кладёт готовые файлы в `vendor/` и управляет ими.

---

## Ошибки и статус

| Уровень | Примеры | Куда |
|---------|---------|------|
| CRITICAL | Нет vendor DLL / winws, нет папки Discord, winws сразу умер | Toast + Status + `data/logs/tray.log` |
| WARN | Автозапуск нужен от админа, SOCKS недоступен, DLL locked | Toast (с debounce) + Status |
| INFO | Restore OK, пресет сохранён, папка Discord обновлена | Лог (+ опционально toast) |

---

## Структура репозитория

```text
discord-proxy-tray/
  src/                 # код
  presets/             # desync JSON; CI updates; offline fallback
  vendor/              # DWrite, force-proxy, zapret bin/lists
  licenses/            # тексты лицензий + NOTICE
  data/                # runtime (не в git)
  scripts/             # генератор пресетов для CI
  .github/workflows/   # обновление пресетов
```

---

## Лицензии

- **Код этого проекта:** [MIT](LICENSE)
- **Сторонние компоненты и атрибуция:** [licenses/NOTICE.md](licenses/NOTICE.md)

Кратко: force-proxy и loader `DWrite.dll` — **GPLv3** (исходники по ссылкам в NOTICE); WinDivert — **LGPLv3 / GPLv2**; zapret/winws — **MIT**.

---

## Отказ от ответственности

Инструмент для доступа к Discord в условиях сетевых ограничений. Используйте на свой риск. Авторы zapret, WinDivert, force-proxy и discord-voice-proxy не связаны с этой обёрткой.
