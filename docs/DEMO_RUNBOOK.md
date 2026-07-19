# Runbook тестовой демо-версии

## 1. Чистая проверка кода

```powershell
python --version
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
.\hotelcut.cmd --help
```

Ожидается: тесты структуры, метаданных, публичного demo-contract и отчетов
проходят. Проверка физических Olymp IV будет пропущена, если локальный корень
не указан.

## 2. Проверка реальных 134 исходников

```powershell
$env:HOTELCUT_OLYMP_ROOT = "C:\Users\SAN-VK\Documents\Codex\AIDAR\OLYMP_4"
python -m unittest discover -s tests -v
```

Ожидается: 134 media ID совпадают; размер и sampled SHA-256 каждого файла не
изменились; профили равны 127 Canon и 7 DJI.

Проверка уже установленного FFmpeg:

```powershell
.\vendor\ffmpeg\ffmpeg.exe -version
.\vendor\ffmpeg\ffprobe.exe -version
```

Если бинарников нет, добровольная локальная установка выполняется скриптом
`.\tools\install_ffmpeg.ps1`. Она требует интернет только на момент загрузки.

## 3. Новый безопасный скан

```powershell
.\hotelcut.cmd scan `
  --hotel-root "$env:HOTELCUT_OLYMP_ROOT" `
  --hotel-id "OLYMP_IV" `
  --output ".\private_outputs\olymp-iv-scan.json"
```

Проверьте `unknown_folders`, `empty_media_folders`, количество файлов и warning.
Сканирование не должно создавать ничего внутри исходной папки отеля.

## 4. Новый metadata report

```powershell
.\hotelcut.cmd metadata `
  --manifest ".\private_outputs\olymp-iv-scan.json" `
  --output ".\private_outputs\olymp-iv-metadata.json"
```

Ожидается `files_requested=134`, `files_read=134`, `files_failed=0`.

## 5. Публичная обезличенная копия

```powershell
python .\tools\sanitize_demo_reports.py `
  .\private_outputs `
  .\outputs
```

Инструмент заменяет абсолютный корень на `${HOTELCUT_OLYMP_ROOT}` и очищает
значения серийных номеров камеры и объектива. Приватные отчеты не коммитьте.

## Критерий приемки 0.2.0

- Все тесты проходят на Python 3.10 или 3.12.
- С переменной `HOTELCUT_OLYMP_ROOT` проходит проверка всех 134 исходников.
- В tracked-отчетах нет личного абсолютного пути и серийных номеров.
- Исходные видео не изменены.
- В документации этапы 1.3–4 явно обозначены как нереализованные.
