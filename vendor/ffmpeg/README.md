# Local FFmpeg runtime

Шаг 1.3 еще не реализован. Этот каталог только фиксирует локальный runtime,
который пользователь установил для следующего этапа.

Проверенная сборка:

- source: BtbN FFmpeg-Builds, `ffmpeg-master-latest-win64-gpl.zip`;
- version: `N-125658-g0869e710e6-20260718`;
- build date marker: 2026-07-18;
- `ffmpeg.exe`: 144544768 bytes, SHA-256 `C1310706C2D12D840CC0212EB8030B6E4E2B3EA2F1845163DCE7E82CFE6B1874`;
- `ffprobe.exe`: 144334336 bytes, SHA-256 `076F6C42CC4764060697BE4B75F89ACD02EDC483D62BC6155C636293E962D417`;
- `ffplay.exe`: 146569728 bytes, SHA-256 `1B0921DD84B01A161B097E11713FC8A8B8CB52C77A6E9C6CE4370752E443C917`.

Бинарники намеренно игнорируются Git. Для повторной загрузки используйте
`tools/install_ffmpeg.ps1`, затем заново проверьте версию и SHA-256.
