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
     release\AudioDNAStudioPro_Setup_1.0.0.exe

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
