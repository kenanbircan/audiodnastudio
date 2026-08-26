# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas = []
binaries = []
hiddenimports = []

for pkg in ("bs_roformer", "demucs", "imageio_ffmpeg", "soundfile", "scipy", "requests", "certifi"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

for dist in ("bs-roformer-infer", "demucs", "torch", "torchaudio", "PySide6", "imageio-ffmpeg", "requests", "certifi"):
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

hiddenimports += collect_submodules("torch")
hiddenimports += collect_submodules("torchaudio")
hiddenimports += collect_submodules("demucs")
hiddenimports += collect_submodules("bs_roformer")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas + [("assets/AudioDNAStudioPro.ico", "assets")],
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AudioDNAStudioPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/AudioDNAStudioPro.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AudioDNAStudioPro",
)
