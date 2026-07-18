# HOTELCUT MVP

Локальный конвейер подготовки гостиничного видеопроекта для Adobe Premiere Pro.

Реализованы шаг 1.1 (безопасное сканирование папки отеля) и шаг 1.2 (чтение и нормализация метаданных через локальный ExifTool). Исходники не изменяются. Прокси пока не создаются.

## Запуск сканера

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m hotelcut scan `
  --hotel-root "C:\Media\2026\COUNTRY\CITY\HOTEL" `
  --hotel-id "HOTEL_ID" `
  --output "$PWD\outputs\project.json"
```

Карта допустимых названий папок находится в `config/folder_map.json`. Созданные системой каталоги `proxies/` и `outbox/` всегда исключаются из повторного сканирования.

## Чтение метаданных

В Windows-версии проекта ExifTool 13.59 находится в `vendor/exiftool/13.59/`. Команда читает все файлы одним процессом и сохраняет результат в новый JSON, не изменяя отчёт шага 1.1:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m hotelcut metadata `
  --manifest "$PWD\outputs\olymp-iv-scan.json" `
  --output "$PWD\outputs\olymp-iv-metadata.json"
```

Для внешней установки ExifTool можно передать `--exiftool "C:\Tools\exiftool.exe"` или задать `HOTELCUT_EXIFTOOL`. Результат содержит длительность, точную дробную частоту кадров, геометрию и поворот, кодеки, аудио, цветовые теги, камеру/объектив, источник времени съёмки и `capture_order` внутри каждой категории. Творческий `edit_order` на этом шаге намеренно не создаётся.
