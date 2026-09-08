# Discord Proxy Tray

Трей-приложение для desktop Discord на Windows: **TCP → локальный SOCKS** и **UDP голос/стримы → DPI desync** (или весь Discord через SOCKS), без системного TUN на весь ПК.

[English](README.en.md)

Репозиторий: https://github.com/neosab3r/discord-proxy-tray

---

## Возможности

- Стратегии **Гибрид** (TCP DLL + winws) и **Полный** (TCP+UDP через SOCKS)
- Раздельные тумблеры **TCP proxy** / **Stream desync** (в Полном stream недоступен)
- Установка `DWrite.dll` + `force-proxy.dll` в Discord `app-*` (кнопка **Установить**, если DLL нет или чужие)
- Детект конфликтов: **drover** (`version.dll` / `drover.ini`) и чужой force-proxy (сравнение SHA256 с `vendor`)
- Мягкое выключение TCP через `PROXY_ENABLED` (DLL остаются на диске)
- Аварийная пауза при **TUN** у VPN: soft-stop + overlay на Modes + восстановление после выключения TUN
- Watcher `app-*` после обновлений Discord; при первой установке DLL — перезапуск Discord при необходимости
- Автозапуск через Task Scheduler (вход, права администратора) с отложенным restore
- Пресеты desync: `presets/` + sync с GitHub + local «последний рабочий»
- Status, Alerts (CRITICAL sticky / WARN toast), логи в `data/logs/`
- About → **Удалить DLL** (только наши файлы в Discord + стоп winws + очистка логов tray)
- Portable: состояние в `data/`, бинарники в `vendor/`

---

## Как это работает

```text
Гибрид:
  Discord.exe
    ├─ TCP  → DWrite.dll → force-proxy-tcp → 127.0.0.1:10808 → v2rayN / Happ
    └─ UDP  → напрямую + winws (WinDivert desync) → Discord media

Полный:
  Discord.exe
    └─ TCP+UDP → DWrite.dll → force-proxy-full → SOCKS5 (в т.ч. UDP ASSOCIATE)
```

Чат, API, CDN — в основном **TCP**. Голос / Go Live / WebRTC — в основном **UDP**.

DLL в Discord всегда называются `DWrite.dll` + `force-proxy.dll`; в `vendor/` лежат две сборки: `force-proxy-tcp.dll` и `force-proxy-full.dll` ([force-proxy-with-logs](https://github.com/neosab3r/force-proxy-with-logs)).

---

## Требования

1. Windows 10/11; для Stream desync / WinDivert — **от администратора**.
2. VPN-клиент с **локальным SOCKS** (по умолчанию `127.0.0.1:10808`), **TUN выключен**, system proxy Clear:
   - **v2rayN** — inbound SOCKS/mixed
   - **Happ** — Start + локальный proxy
3. Desktop Discord.

Бинарники sidecar в `vendor/` (см. [licenses/NOTICE.md](licenses/NOTICE.md)).

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

Если в Discord нет наших DLL — на вкладке **Modes** overlay → **Установить** (перезапуск Discord, включается Полный).  
Дальше можно переключиться на **Гибрид** и включить Stream desync + пресет.

### Portable release

Скачайте zip с [Releases](https://github.com/neosab3r/discord-proxy-tray/releases), распакуйте и запустите `DiscordProxyTray.exe` (лучше от администратора для Stream / WinDivert). Рядом лежит ярлык с `--open-panel`. Состояние пишется в `data/` внутри папки.

Сборка из исходников: `powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1 -Zip`.

---

## Режимы

| Стратегия | TCP | Stream | Типичный результат |
|-----------|-----|--------|--------------------|
| Гибрид | ON | ON | Чат через SOCKS + голос/стримы через winws |
| Гибрид | ON | OFF | Чат ок; guild voice часто «Не установлен маршрут» |
| Полный | ON | — | Чат + голос через SOCKS UDP ASSOCIATE (пресеты не используются) |
| любой | OFF | OFF | Soft-off TCP + останов winws |

**Голос:** для guild voice обычно стабильнее **Гибрид + Stream + пресет вроде `alt12`** (полный list-general, не только `*-discord-only`). В Полном вход в канал часто ок, но аудио/видео через SOCKS UDP бывает нестабильно — это ограничение UDP ASSOCIATE у многих клиентов, не только tray.

Адрес SOCKS (host:port) на вкладке Modes: сохраняется при **Enter** или потере фокуса; опрос статуса его не перезаписывает.

Не совмещайте с **TUN** у VPN-клиента — приложение ставит аварийную паузу.

---

## Пресеты

| Слой | Где |
|------|-----|
| Репозиторий / CI | `presets/` — источник правды, Action обновляет раз в день |
| Кэш приложения | `data/presets/remote/` — скачивается с GitHub, если `version.txt` новее |
| Ваши | `data/presets/local/` — last working и ручные копии |

Порядок: **local → remote → `presets/` рядом с приложением**.  
URL по умолчанию: `…/master/presets`. CI: `.github/workflows/update-presets.yml` из [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).

---

## Архитектура

```text
Tray (Python / PySide6)
  ├─ install / soft PROXY_ENABLED + watcher Discord app-*
  ├─ TUN check + emergency pause
  └─ winws + пресеты + WinDivert (только Гибрид)
```

Конфиг и логи: `data/`.  
Sidecar: `vendor/DWrite.dll`, `vendor/force-proxy-*.dll`, `vendor/zapret/`.

---

## Стек

| Слой | Технологии |
|------|------------|
| Приложение | Python 3.11+, PySide6, httpx, psutil |
| TCP / Full | discord-voice-proxy `DWrite.dll` + [force-proxy-with-logs](https://github.com/neosab3r/force-proxy-with-logs) |
| UDP (Гибрид) | winws + WinDivert (Flowseal / bol-van zapret) |

---

## Ошибки и статус

| Уровень | Примеры | Куда |
|---------|---------|------|
| CRITICAL | Нет vendor / winws, нет папки Discord | Toast + sticky tooltip + Status |
| WARN | SOCKS down, TUN, DLL locked | Toast (раз за сессию на код) + Status |
| INFO | Restore, установка DLL, смена стратегии | Лог / toast |

---

## Структура репозитория

```text
discord-proxy-tray/
  src/                 # код
  presets/             # desync JSON; CI; offline fallback
  vendor/              # DWrite, force-proxy-tcp/full, zapret
  licenses/            # тексты лицензий + NOTICE
  data/                # runtime (не в git)
  scripts/             # CI / release
  .github/workflows/
```

---

## Лицензии

- **Код этого проекта:** [MIT](LICENSE)
- **Сторонние компоненты:** [licenses/NOTICE.md](licenses/NOTICE.md)

force-proxy и `DWrite.dll` — **GPLv3**; WinDivert — **LGPLv3 / GPLv2**; zapret/winws — **MIT**.

---

## Отказ от ответственности

Инструмент для доступа к Discord в условиях сетевых ограничений. Используйте на свой риск. Авторы zapret, WinDivert, force-proxy и discord-voice-proxy не связаны с этой обёрткой.
