AUDIO DNA STUDIO PRO — WINDOWS 11 RELEASE PROJECT
=================================================

WHAT THIS IS
------------
A full Windows 11 desktop application project for offline music stem extraction.

Stem inference runs directly inside the installed desktop program. There is no
stem-extraction API and no web server.

Core separation:
- BS-RoFormer 6-stem: vocals, drums, bass, guitar, piano, other
- Demucs htdemucs_ft: independent vocals, drums, bass, other
- Maximum Accuracy mode ensembles both model families
- Residual vocal-correlation cleanup on instrument stems
- Rebuilt instrumental from cleaned instrument stems
- 24-bit WAV output

The program also includes:
- Individual stem Play
- Play Selection
- Pause / Stop
- Timeline seeking
- +/- 5 second seeking
- Per-stem WAV export
- Custom stem mix render
- Local model cache
- Local projects folder
- Download / Verify AI Models button
- PyTorch/CUDA diagnostics

FIRST BUILD ON WINDOWS 11
-------------------------
1. Install Python 3.11 or 3.12 x64.
2. Double-click BUILD_WINDOWS11_RELEASE.bat.
3. The builder creates:
     dist\AudioDNAStudioPro\AudioDNAStudioPro.exe

If Inno Setup 6 is installed, it also creates:
     release\AudioDNAStudioPro_Setup_1.1.0.exe

The EXE contains the application and Python dependencies, including a packaged
FFmpeg binary via imageio-ffmpeg. AI checkpoint files are intentionally stored
outside the EXE because they are very large.

FIRST RUN
---------
1. Launch Audio DNA Studio Pro.
2. Open Diagnostics / Log.
3. Click "Download / Verify AI Models".
4. The program downloads and verifies the model weights to:
     %LOCALAPPDATA%\AudioDNAStudioPro\models
5. After the weights are present, stem extraction can run offline.

PROJECTS
--------
Projects are stored under:
  %LOCALAPPDATA%\AudioDNAStudioPro\projects

BUILD AUTOMATION
----------------
The project includes:
  .github\workflows\build-windows.yml

Running this workflow on GitHub's Windows runner builds the EXE and the Inno
Setup installer and uploads them as workflow artifacts.

WHY THE MODEL FILES ARE NOT INSIDE THE EXE
------------------------------------------
The recommended BS-RoFormer model alone is roughly 700 MB, and Demucs adds
additional model data. Keeping model weights in the user's local model cache
makes application updates smaller and avoids duplicating gigabytes of weights.

OFFLINE OPERATION
-----------------
The application needs internet only when model weights are first downloaded.
Once the models are cached locally, stem inference does not use an extraction API.

WINDOWS EXE BUILD NOTE
----------------------
PyInstaller must run on Windows to create a Windows executable. The project
contains the complete Windows build configuration and installer definition.

V1.1 BS-ROFORMER FIX
--------------------
The v1.0 build incorrectly checked for BSRoformerSession, which is not in the
released bs-roformer-infer 0.1.5 API. v1.1 uses the released inference entry:
  from bs_roformer.inference import proc_folder

The GitHub workflow now verifies BS-RoFormer before packaging and runs a
packaged dependency self-check after PyInstaller.


V1.2 CHECKPOINT DOWNLOAD FIX
----------------------------
Automatic model setup now tries the package downloader, then a resumable HTTPS download using requests + certifi. If that is blocked, use Diagnostics / Log -> Import BS-RoFormer Checkpoint.

Expected file: BS-Rofo-SW-Fixed.ckpt
Expected size: 699,412,152 bytes
Expected SHA-256: 24e7d35ee9c64415673d3fd33e06a67cac2c103c5df6267ba1576459c775916e
Expected local path: %LOCALAPPDATA%\AudioDNAStudioPro\models\roformer\roformer-model-bs-roformer-sw-by-jarredou\BS-Rofo-SW-Fixed.ckpt


V1.3 NONETYPE.WRITE / INFERENCE FIX
------------------------------------
- Adds a PyInstaller runtime hook that supplies devnull-backed stdin/stdout/stderr
  before PyTorch, tqdm, Demucs or BS-RoFormer import.
- Adds the same guard in app.py and multiprocessing.freeze_support().
- BS-RoFormer inference now verifies/resolves the local checkpoint first and
  passes --model_path and --config_path explicitly, so inference cannot silently
  enter the checkpoint downloader.
- Fixes: AttributeError: 'NoneType' object has no attribute 'write'.


V1.4 GITHUB BUILD FIX
---------------------
The external PyInstaller runtime hook has been removed.

The Windows stdout/stderr compatibility guard is now entirely embedded at the
top of app.py, before PySide6, engine, PyTorch, Demucs, or BS-RoFormer imports.

This removes the build dependency on:
  runtime_hooks/pyi_stream_fix.py

The GitHub workflow no longer references the runtime_hooks folder, which makes
browser-based repository uploads much more reliable.

Expected installer:
  AudioDNAStudioPro_Setup_1.4.0.exe
