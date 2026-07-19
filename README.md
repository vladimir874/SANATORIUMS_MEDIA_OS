# SANATORIUMS MEDIA OS — HOTELCUT

Финальная тестовая демо-версия локального конвейера подготовки гостиничных
видеоматериалов. Репозиторий объединяет знания SANATORIUMS MEDIA OS и
проверенное ядро HOTELCUT, не выдавая будущие этапы за готовую автоматизацию.

## Что действительно готово

| Блок | Статус | Проверка |
|---|---|---|
| 1.1 Сканирование структуры | стабильно, утверждено | 134/134 MP4 Olymp IV |
| 1.2 Метаданные ExifTool | стабильно, утверждено | 134 прочитано, 0 ошибок |
| 1.3 Прокси FFmpeg | не начато | локальный FFmpeg установлен, код прокси отсутствует |
| 2 Сцены и техбрак | не начато | — |
| 3 Черновой таймлайн Premiere | архитектура, без реализации | — |
| 4 Аудит таймлайна | не начато | — |

Исходные медиа сканер не перемещает, не переименовывает и не изменяет.

## Состав репозитория

- `src/hotelcut/` — рабочее Python-ядро шагов 1.1–1.2.
- `config/` — редактируемая карта папок Sanatoriums.
- `vendor/exiftool/` — локальный ExifTool 13.59 для Windows.
- `vendor/ffmpeg/` — локальный FFmpeg runtime (бинарники не публикуются в Git).
- `outputs/` — обезличенные контрольные отчеты Olymp IV.
- `00_Core/`, `01_Agents/` — операционная база знаний Media OS.
- `apps-script/`, `prompts/`, `templates/` — вспомогательный трекер производства.
- `experiments/` — изолированные прототипы, не являющиеся HOTELCUT.
- `docs/` — архитектура, память решений и сценарий проверки демо.

Полная карта: [docs/REPOSITORY_MAP.md](docs/REPOSITORY_MAP.md).

## Быстрый запуск

Требуется Python 3.10–3.12. Облачные сервисы и установка пакетов не нужны.
Windows-launcher находит обычный Python, runtime Codex или путь из
`HOTELCUT_PYTHON`.

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
.\hotelcut.cmd --help
```

Сканирование папки отеля:

```powershell
.\hotelcut.cmd scan `
  --hotel-root "C:\Media\COUNTRY\CITY\HOTEL" `
  --hotel-id "HOTEL_ID" `
  --output ".\private_outputs\project-scan.json"
```

Чтение метаданных одним локальным процессом ExifTool:

```powershell
.\hotelcut.cmd metadata `
  --manifest ".\private_outputs\project-scan.json" `
  --output ".\private_outputs\project-metadata.json"
```

При необходимости укажите внешний ExifTool через `--exiftool` или переменную
`HOTELCUT_EXIFTOOL`. На Windows по умолчанию используется включенная версия
`vendor/exiftool/13.59/exiftool.exe`.

## Реальная проверка Olymp IV

Публичные отчеты не содержат имя пользователя, абсолютные пути и серийные
номера камеры. Для повторной проверки всех исходников задайте локальный корень:

```powershell
$env:HOTELCUT_OLYMP_ROOT = "C:\path\to\OLYMP_4"
python -m unittest discover -s tests -v
```

Без этой переменной только проверка физических файлов будет корректно
пропущена; структура и технические профили отчетов продолжат проверяться.

## Граница Premiere Pro

Текущая демо-версия еще не строит таймлайн. Подтвержденный целевой путь:
локальный Python/FFmpeg создает manifest, затем тонкий UXP-модуль собирает
последовательность в Premiere Pro. Старый замысел FCPXML сохранен в истории,
но FCPXML нельзя считать прямым и проверенным импортом Premiere.

На тестовой машине FFmpeg уже найден и проверен командой `-version`, но это не
означает реализацию прокси. Следующий разрешенный шаг — только 1.3: локальные
прокси с сохранением исходных
50 и 60000/1001 fps. Подробности: [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md)
и [project_status.json](project_status.json).
