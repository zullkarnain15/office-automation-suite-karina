# Application Update Onefile Updater Fix Report

## Root Cause

`UpdaterLauncher` treated the updater source as a directory and defaulted to the source tree path `updater`. In a PyInstaller onefile build, the application runs from the temporary extraction root `sys._MEIPASS`, so the GUI attempted to find a bundled folder like:

```text
C:\Users\User\AppData\Local\Temp\_MEI85162\updater
```

The application actually needs the standalone updater executable file, not a source directory. The onefile application spec also did not previously guarantee that `OAS-K-Updater.exe` was bundled into the app.

## Fix

- Added centralized updater resource resolution for development, PyInstaller onefile, and PyInstaller onedir modes.
- Frozen builds now resolve the actual bundled file:

```text
updater\OAS-K-Updater.exe
```

- The updater is copied from the bundled resource into Data Root runtime before launch.
- The updater is launched from Data Root runtime, not from `_MEIPASS`.
- Missing frozen updater now raises:

```text
OAS-K-Updater.exe tidak ditemukan dalam paket aplikasi.
```

## Files Changed

- `OAS-K.spec`
- `shared/update/updater_launcher.py`
- `shared/update/updater_resource.py`
- `tests/update/test_updater_resource.py`

## Bundled Updater Path

Inside the PyInstaller onefile archive:

```text
updater\OAS-K-Updater.exe
```

Build inspection confirmed this entry in `Analysis-00.toc`, `PKG-00.toc`, `EXE-00.toc`, and `pyi-archive_viewer`.

## Runtime Updater Path

GUI retest copied the updater to:

```text
D:\OAS-K_Restricted_Environment_Test\Data\update\runtime\9830172f-c233-4d90-b0df-fb707f38c186\OAS-K-Updater.exe
```

Runtime updater SHA-256:

```text
e3ce3ce526c2f78e47dfcbbb3bea30927cdfc11a39bea144c3f61639faa5a3f0
```

## Build Result

Updater build:

```text
py tools\build_updater.py
```

- Output: `dist\updater\OAS-K-Updater.exe`
- SHA-256: `e3ce3ce526c2f78e47dfcbbb3bea30927cdfc11a39bea144c3f61639faa5a3f0`

Application build:

```text
py -m PyInstaller --noconfirm --clean OAS-K.spec
```

- Output: `dist\OAS-K.exe`
- SHA-256: `5483366c3c85dc87d3d822ab57325b8264d55f39fd04438945c0c7d45f60217d`

Restricted sandbox fixed builds:

- Baseline `1.0.0-sandbox`: `5e487bc5bb15cd2e921f188efbeab1e3d49bf0ac86f2bb6ff73c310c18ce7f67`
- Target `1.0.1-sandbox`: `d6062b38de3eb1ff8e911c8d04ca1a9c98f50423239dbf81365a898c4bcd4904`
- Update package `1.0.1-sandbox`: `13935c012546ab9d2a80fd56b8bb1e6887fb2a9b7487bbe22a4446c448297ae3`

## GUI Update Retest

Sandbox:

```text
D:\OAS-K_Restricted_Environment_Test
```

GUI flow executed from fixed onefile OAS-K:

1. Opened OAS-K fixed baseline.
2. Opened Settings.
3. Opened Application Update.
4. Selected fixed ZIP package.
5. Validated package.
6. Prepared update.
7. Clicked Close and Apply Update.
8. Confirmed apply.
9. OAS-K restarted successfully.

Result:

- Transaction ID: `9830172f-c233-4d90-b0df-fb707f38c186`
- Final status: `SUCCESS`
- Health-check version: `1.0.1-sandbox`
- Active application SHA-256 after update: `d6062b38de3eb1ff8e911c8d04ca1a9c98f50423239dbf81365a898c4bcd4904`
- Database SHA-256 unchanged: `ec04688e4b1d4f32af4939bb7ca18c8cd8fd25255c9097886504cc14978d0dd0`
- Recorder profile SHA-256 unchanged: `e5d8f091a701b42a7bb6c87bad2568a94d1e66f6eaa7cdb2dbf024ac7ba53eaf`
- Previous `_MEIPASS\updater` error: not reproduced.

## Test Result

```text
py -m pytest tests\update -v
49 passed, 1 warning

py -m pytest
707 passed, 1 warning

git diff --check
passed
```

The warning is the intentional duplicate ZIP path validator test.
