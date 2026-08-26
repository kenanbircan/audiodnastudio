from __future__ import annotations

import os
import sys
import math
import shutil
import subprocess
import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf


class EngineError(RuntimeError):
    pass

ROFORMER_SLUG = "roformer-model-bs-roformer-sw-by-jarredou"
ROFORMER_FILENAME = "BS-Rofo-SW-Fixed.ckpt"
ROFORMER_URL = "https://huggingface.co/enerjazzer/BS-ROFO-SW-Fixed/resolve/main/BS-Rofo-SW-Fixed.ckpt"
ROFORMER_SHA256 = "24e7d35ee9c64415673d3fd33e06a67cac2c103c5df6267ba1576459c775916e"
ROFORMER_SIZE = 699_412_152


def user_data_root() -> Path:
    override = os.getenv("AUDIO_DNA_DATA")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home()))
        return base / "AudioDNAStudioPro"
    return Path.home() / ".audiodna-studio-pro"


def bundled_ffmpeg() -> str | None:
    # imageio-ffmpeg ships a platform ffmpeg binary inside the package.
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


class StemEngine:
    STEMS6 = ("vocals", "drums", "bass", "guitar", "piano", "other")

    def __init__(self, app_dir: Path | None = None):
        self.app_dir = Path(app_dir or Path(sys.executable).resolve().parent)
        self.data_dir = user_data_root()
        self.models_dir = self.data_dir / "models"
        self.roformer_models = self.models_dir / "roformer"
        self.demucs_models = self.models_dir / "demucs"
        self.projects_dir = self.data_dir / "projects"
        for p in (self.models_dir, self.roformer_models, self.demucs_models, self.projects_dir):
            p.mkdir(parents=True, exist_ok=True)

    def _set_model_env(self):
        os.environ["BS_ROFORMER_MODELS_PATH"] = str(self.roformer_models)
        os.environ["TORCH_HOME"] = str(self.demucs_models)
        os.environ["XDG_CACHE_HOME"] = str(self.models_dir)
        try:
            import certifi
            os.environ["SSL_CERT_FILE"] = certifi.where()
            os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
        except Exception:
            pass

    @property
    def roformer_checkpoint_path(self) -> Path:
        return self.roformer_models / ROFORMER_SLUG / ROFORMER_FILENAME

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify_roformer_checkpoint(self, path: Path | None = None) -> dict:
        path = Path(path or self.roformer_checkpoint_path)
        if not path.exists():
            return {"ok": False, "reason": "missing", "path": str(path)}
        size = path.stat().st_size
        if size != ROFORMER_SIZE:
            return {"ok": False, "reason": "size_mismatch", "path": str(path), "size": size, "expected_size": ROFORMER_SIZE}
        digest = self._sha256_file(path)
        return {"ok": digest.lower() == ROFORMER_SHA256.lower(), "reason": "ok" if digest.lower() == ROFORMER_SHA256.lower() else "sha256_mismatch", "path": str(path), "size": size, "sha256": digest, "expected_sha256": ROFORMER_SHA256}

    def import_roformer_checkpoint(self, source: Path) -> dict:
        source = Path(source)
        if not source.exists():
            raise EngineError("Selected checkpoint file does not exist.")
        if source.stat().st_size != ROFORMER_SIZE:
            raise EngineError(f"Wrong checkpoint size: {source.stat().st_size:,} bytes. Expected {ROFORMER_SIZE:,} bytes.")
        digest = self._sha256_file(source)
        if digest.lower() != ROFORMER_SHA256.lower():
            raise EngineError(f"Checkpoint SHA-256 verification failed. Expected {ROFORMER_SHA256}, got {digest}.")
        target = self.roformer_checkpoint_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix('.ckpt.importing')
        shutil.copy2(source, tmp)
        tmp.replace(target)
        return self.verify_roformer_checkpoint(target)

    def _download_roformer_checkpoint_direct(self, progress=None) -> Path:
        self._set_model_env()
        target = self.roformer_checkpoint_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix('.ckpt.part')
        try:
            import requests
        except Exception as exc:
            raise EngineError("Python requests package is unavailable in this build.") from exc
        headers = {"User-Agent": "AudioDNAStudioPro/1.2"}
        downloaded = tmp.stat().st_size if tmp.exists() else 0
        if downloaded > ROFORMER_SIZE:
            tmp.unlink(missing_ok=True); downloaded = 0
        if downloaded:
            headers["Range"] = f"bytes={downloaded}-"
        try:
            with requests.get(ROFORMER_URL, stream=True, timeout=(20,120), headers=headers, allow_redirects=True) as response:
                if response.status_code == 416:
                    tmp.unlink(missing_ok=True)
                    return self._download_roformer_checkpoint_direct(progress)
                if response.status_code not in (200,206):
                    raise EngineError(f"Checkpoint host returned HTTP {response.status_code}: {response.text[:300]}")
                if response.status_code == 200 and downloaded:
                    tmp.unlink(missing_ok=True); downloaded = 0
                mode = 'ab' if response.status_code == 206 and downloaded else 'wb'
                with tmp.open(mode) as fh:
                    current = downloaded
                    for chunk in response.iter_content(chunk_size=4*1024*1024):
                        if not chunk: continue
                        fh.write(chunk); current += len(chunk)
                        if progress:
                            progress(min(95, int(current/ROFORMER_SIZE*95)), f"BS-RoFormer checkpoint {current/1024/1024:.0f} / {ROFORMER_SIZE/1024/1024:.0f} MB")
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError("Could not download the BS-RoFormer checkpoint. Download it in your browser and use Import BS-RoFormer Checkpoint. Details: " + str(exc)) from exc
        if tmp.stat().st_size != ROFORMER_SIZE:
            raise EngineError(f"Checkpoint download incomplete: {tmp.stat().st_size:,} bytes; expected {ROFORMER_SIZE:,}.")
        digest = self._sha256_file(tmp)
        if digest.lower() != ROFORMER_SHA256.lower():
            tmp.unlink(missing_ok=True)
            raise EngineError("Downloaded checkpoint failed SHA-256 verification; corrupt file removed.")
        tmp.replace(target)
        return target

    def system_info(self):
        self._set_model_env()
        ffmpeg = bundled_ffmpeg()
        try:
            import bs_roformer  # noqa: F401
            from bs_roformer.inference import proc_folder  # noqa: F401
            from bs_roformer import DEFAULT_MODEL, ensure_model_assets  # noqa: F401
            roformer = True
        except Exception:
            roformer = False
        try:
            import demucs  # noqa
            demucs_ok = True
        except Exception:
            demucs_ok = False
        try:
            import torch
            torch_ok = True
            cuda = bool(torch.cuda.is_available())
            cuda_name = torch.cuda.get_device_name(0) if cuda else ""
        except Exception:
            torch_ok = False
            cuda = False
            cuda_name = ""
        checkpoint = self.verify_roformer_checkpoint()
        return {
            "python": sys.version.split()[0],
            "ffmpeg": bool(ffmpeg),
            "ffmpeg_path": ffmpeg or "",
            "roformer": roformer,
            "roformer_checkpoint": checkpoint.get("ok", False),
            "roformer_checkpoint_path": checkpoint.get("path", str(self.roformer_checkpoint_path)),
            "demucs": demucs_ok,
            "torch": torch_ok,
            "cuda": cuda,
            "cuda_name": cuda_name,
            "models_dir": str(self.models_dir),
            "projects_dir": str(self.projects_dir),
            "ready": bool(ffmpeg and torch_ok and roformer and demucs_ok),
        }

    def download_models(self, progress=None):
        self._set_model_env()
        def report(p,m):
            if progress: progress(int(p), str(m))
        report(2, "Checking BS-RoFormer checkpoint cache…")
        check = self.verify_roformer_checkpoint()
        if not check["ok"]:
            report(5, "BS-RoFormer checkpoint missing; trying package downloader…")
            package_error = None
            try:
                from bs_roformer import DEFAULT_MODEL, ensure_model_assets
                ckpt, cfg = ensure_model_assets(DEFAULT_MODEL, models_dir=self.roformer_models)
                check = self.verify_roformer_checkpoint(Path(ckpt))
            except Exception as exc:
                package_error = str(exc)
                check = self.verify_roformer_checkpoint()
            if not check["ok"]:
                report(8, "Package downloader failed; trying resumable direct download…")
                try:
                    ckpt = self._download_roformer_checkpoint_direct(lambda p,m: report(8 + int(p*0.48), m))
                    check = self.verify_roformer_checkpoint(ckpt)
                except Exception as direct_exc:
                    raise EngineError("BS-RoFormer checkpoint download failed.\n\nDownload BS-Rofo-SW-Fixed.ckpt in your browser, then use Diagnostics / Log -> Import BS-RoFormer Checkpoint.\n\nPackage downloader: " + (package_error or "not available") + "\nDirect downloader: " + str(direct_exc)) from direct_exc
        if not check["ok"]:
            raise EngineError("BS-RoFormer checkpoint is not valid after download.")
        report(58, "BS-RoFormer checkpoint verified.")
        try:
            from bs_roformer import DEFAULT_MODEL, ensure_model_assets
            ckpt, cfg = ensure_model_assets(DEFAULT_MODEL, models_dir=self.roformer_models)
        except Exception as exc:
            raise EngineError(f"BS-RoFormer config resolution failed: {exc}") from exc
        report(62, "Checking Demucs htdemucs_ft model…")
        try:
            from demucs.pretrained import get_model
            get_model("htdemucs_ft")
            report(100, "All neural model files are ready for offline use.")
        except Exception as exc:
            raise EngineError(f"Demucs model download failed: {exc}") from exc
        return {"roformer_checkpoint": str(ckpt), "roformer_config": str(cfg), "checkpoint_sha256": ROFORMER_SHA256}

    def separate(self, source, project_dir=None, mode="maximum", cleanup="strong", progress=None):
        self._set_model_env()
        source = Path(source)
        if project_dir is None:
            project_dir = self.projects_dir / source.stem
        project_dir = Path(project_dir)
        work = project_dir / "working"
        final = project_dir / "stems"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        final.mkdir(parents=True, exist_ok=True)

        def report(p, msg):
            if progress:
                progress(int(p), str(msg))

        report(2, "Preparing 44.1 kHz stereo source…")
        normalized = work / "input" / f"{source.stem}.wav"
        normalized.parent.mkdir(parents=True)
        self._ffmpeg_convert(source, normalized)

        if mode == "roformer":
            report(8, "Running BS‑RoFormer 6‑stem model locally…")
            stems = self._run_roformer(normalized, work / "roformer", report)
            result = self._copy_final(stems, final)
            if "instrumental" not in result:
                self._build_instrumental(result, final / "instrumental.wav")
                result["instrumental"] = final / "instrumental.wav"
            report(100, "BS‑RoFormer extraction complete.")
            return {"engine": "BS‑RoFormer 6‑Stem", "stems": stringify(result), "qc": {}}

        if mode == "demucs":
            report(8, "Running Demucs htdemucs_ft locally…")
            stems = self._run_demucs(normalized, work / "demucs", report)
            result = self._copy_final(stems, final)
            self._build_instrumental(result, final / "instrumental.wav")
            result["instrumental"] = final / "instrumental.wav"
            report(100, "Demucs extraction complete.")
            return {"engine": "Demucs htdemucs_ft", "stems": stringify(result), "qc": {}}

        report(6, "Pass 1/2 — BS‑RoFormer 6‑stem local inference…")
        ro = self._run_roformer(normalized, work / "roformer", lambda p, m: report(6 + p * 0.43, m))
        report(50, "Pass 2/2 — Demucs htdemucs_ft local inference…")
        de = self._run_demucs(normalized, work / "demucs", lambda p, m: report(50 + p * 0.27, m))
        report(78, "Ensembling independent model estimates…")
        result, qc = self._ensemble(ro, de, final, cleanup, report)
        report(100, "Maximum Accuracy extraction complete.")
        return {
            "engine": "BS‑RoFormer + Demucs htdemucs_ft ensemble",
            "stems": stringify(result),
            "qc": qc,
        }

    def _ffmpeg_convert(self, src, dst):
        ffmpeg = bundled_ffmpeg()
        if not ffmpeg:
            raise EngineError("FFmpeg is not available in this build.")
        self._run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src), "-ar", "44100", "-ac", "2",
            "-c:a", "pcm_f32le", str(dst)
        ], "Audio conversion failed")

    def _run_roformer(self, normalized, out_dir, progress):
        input_dir = out_dir / "input"
        store_dir = out_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        store_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(normalized, input_dir / normalized.name)

        progress(5, "Loading BS‑RoFormer 0.1.5 inference engine…")
        try:
            import torch
            from bs_roformer import DEFAULT_MODEL, ensure_model_assets
            from bs_roformer.inference import proc_folder
            device = "cuda:0" if torch.cuda.is_available() else "cpu"

            # Verify and resolve the local checkpoint before inference, then
            # pass both checkpoint and config explicitly. This prevents the
            # inference CLI from entering its downloader path at runtime.
            checkpoint = self.verify_roformer_checkpoint()
            if not checkpoint.get("ok"):
                raise EngineError(
                    "BS-RoFormer checkpoint is missing or invalid. Use Diagnostics / Log -> "
                    "Download / Verify AI Models or Import BS-RoFormer Checkpoint."
                )
            ckpt_path, config_path = ensure_model_assets(
                DEFAULT_MODEL, models_dir=self.roformer_models
            )
            progress(12, f"BS‑RoFormer running on {device.upper()}…")
            proc_folder([
                "--input_folder", str(input_dir),
                "--store_dir", str(store_dir),
                "--model_path", str(ckpt_path),
                "--config_path", str(config_path),
                "--device", device,
            ])
        except SystemExit as exc:
            code = int(getattr(exc, "code", 1) or 0)
            if code != 0:
                raise EngineError(f"BS‑RoFormer exited with code {code}") from exc
        except Exception as exc:
            raise EngineError(f"BS‑RoFormer inference failed: {exc}") from exc

        stems = self._locate_roformer_stems(store_dir)
        missing = [s for s in self.STEMS6 if s not in stems]
        if missing:
            raise EngineError("BS‑RoFormer did not create: " + ", ".join(missing))
        progress(100, "BS‑RoFormer pass complete.")
        return stems

    def _run_demucs(self, normalized, out_dir, progress):
        out_dir.mkdir(parents=True, exist_ok=True)
        progress(5, "Loading Demucs htdemucs_ft…")
        args = [
            "-n", "htdemucs_ft",
            "--out", str(out_dir),
            "--float32",
            "--clip-mode", "clamp",
            "--shifts", "2",
            "--overlap", "0.50",
            str(normalized),
        ]
        try:
            from demucs.separate import main as demucs_main
            progress(12, "Demucs separation running…")
            demucs_main(args)
        except SystemExit as exc:
            if int(getattr(exc, "code", 1) or 0) != 0:
                raise EngineError(f"Demucs exited with code {exc.code}") from exc
        except Exception as exc:
            raise EngineError(f"Demucs inference failed: {exc}") from exc

        stems = {}
        for name in ("vocals", "drums", "bass", "other"):
            found = list(out_dir.rglob(f"{name}.wav"))
            if found:
                stems[name] = max(found, key=lambda p: p.stat().st_size)
        missing = [s for s in ("vocals", "drums", "bass", "other") if s not in stems]
        if missing:
            raise EngineError("Demucs did not create: " + ", ".join(missing))
        progress(100, "Demucs pass complete.")
        return stems

    def _locate_roformer_stems(self, folder):
        stems = {}
        folder = Path(folder)
        for stem in (*self.STEMS6, "instrumental"):
            matches = [p for p in folder.rglob("*.wav") if stem in p.stem.lower()]
            if matches:
                stems[stem] = max(matches, key=lambda p: p.stat().st_size)
        return stems

    def _ensemble(self, ro, de, final, cleanup, progress):
        strength, max_alpha, threshold = {
            "conservative": (0.34, 0.24, 0.18),
            "strong": (0.55, 0.38, 0.13),
            "aggressive": (0.75, 0.52, 0.09),
        }[cleanup]

        ro_audio = {k: read_audio(v)[0] for k, v in ro.items() if k in self.STEMS6}
        de_audio = {k: read_audio(v)[0] for k, v in de.items()}

        vocal = weighted_mix([(ro_audio["vocals"], 0.68), (de_audio["vocals"], 0.32)])
        base = {
            "drums": weighted_mix([(ro_audio["drums"], 0.80), (de_audio["drums"], 0.20)]),
            "bass": weighted_mix([(ro_audio["bass"], 0.80), (de_audio["bass"], 0.20)]),
            "guitar": ro_audio["guitar"],
            "piano": ro_audio["piano"],
            "other": ro_audio["other"],
        }

        result, qc = {}, {}
        write_audio(final / "vocals.wav", vocal, 44100)
        result["vocals"] = final / "vocals.wav"

        for idx, name in enumerate(("drums", "bass", "guitar", "piano", "other")):
            before = correlation_score(base[name], vocal)
            cleaned = projection_cleanup(base[name], vocal, strength, max_alpha, threshold)
            after = correlation_score(cleaned, vocal)
            qc[name] = {"before": round(before, 4), "after": round(after, 4)}
            path = final / f"{name}.wav"
            write_audio(path, cleaned, 44100)
            result[name] = path
            progress(80 + idx * 3, f"{name}: vocal correlation {before:.3f} → {after:.3f}")

        instrumental = sum_tracks([read_audio(result[n])[0] for n in ("drums","bass","guitar","piano","other")])
        write_audio(final / "instrumental.wav", instrumental, 44100)
        result["instrumental"] = final / "instrumental.wav"
        qc["instrumental"] = {"vocal_correlation": round(correlation_score(instrumental, vocal), 4)}
        return result, qc

    def _copy_final(self, stems, final):
        result = {}
        for name, src in stems.items():
            dst = final / f"{name}.wav"
            self._ffmpeg_wav24(src, dst)
            result[name] = dst
        return result

    def _build_instrumental(self, stems, out):
        parts = [stems[k] for k in ("drums","bass","guitar","piano","other") if k in stems]
        if not parts:
            parts = [stems[k] for k in ("drums","bass","other") if k in stems]
        self.render_mix(parts, out)

    def render_mix(self, inputs, out):
        if not inputs:
            raise EngineError("No stems selected.")
        ffmpeg = bundled_ffmpeg()
        if not ffmpeg:
            raise EngineError("FFmpeg is not available.")
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for p in inputs:
            cmd += ["-i", str(p)]
        cmd += [
            "-filter_complex", f"amix=inputs={len(inputs)}:duration=longest:normalize=0",
            "-c:a", "pcm_s24le", str(out)
        ]
        self._run(cmd, "Mix render failed")

    def _ffmpeg_wav24(self, src, dst):
        ffmpeg = bundled_ffmpeg()
        self._run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src), "-c:a", "pcm_s24le", str(dst)
        ], "WAV export failed")

    def _run(self, cmd, label):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise EngineError(f"{label}:\n{(p.stderr or p.stdout)[-5000:]}")


def stringify(d):
    return {k: str(v) for k, v in d.items()}


def read_audio(path):
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    if sr != 44100:
        raise EngineError(f"Unexpected sample rate {sr} in {Path(path).name}.")
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    return data, sr


def write_audio(path, data, sr):
    sf.write(str(path), peak_normalize(data), sr, subtype="PCM_24")


def align_arrays(*arrays):
    length = min(a.shape[0] for a in arrays)
    channels = min(a.shape[1] for a in arrays)
    return [a[:length, :channels].copy() for a in arrays]


def weighted_mix(items):
    arrays = align_arrays(*[x for x, _ in items])
    weights = [w for _, w in items]
    denom = sum(weights) or 1.0
    out = np.zeros_like(arrays[0], dtype=np.float32)
    for arr, w in zip(arrays, weights):
        out += arr * (w / denom)
    return peak_normalize(out)


def sum_tracks(arrays):
    arrays = align_arrays(*arrays)
    out = np.zeros_like(arrays[0], dtype=np.float32)
    for arr in arrays:
        out += arr
    return peak_normalize(out)


def peak_normalize(data, target=0.985):
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > target and peak > 0:
        data = data * (target / peak)
    return data.astype(np.float32, copy=False)


def correlation_score(target, vocal):
    target, vocal = align_arrays(target, vocal)
    stride = max(1, target.shape[0] // 400000)
    x = target[::stride].reshape(-1).astype(np.float64)
    v = vocal[::stride].reshape(-1).astype(np.float64)
    denom = math.sqrt(float(np.dot(x, x)) * float(np.dot(v, v))) + 1e-12
    return abs(float(np.dot(x, v)) / denom)


def projection_cleanup(target, vocal, strength, max_alpha, threshold):
    target, vocal = align_arrays(target, vocal)
    out = target.copy()
    win = int(44100 * 0.35)
    hop = win // 2
    edge = max(128, int(win * 0.08))
    for start in range(0, max(1, out.shape[0] - 1), hop):
        end = min(out.shape[0], start + win)
        if end - start < 1024:
            break
        x, v = target[start:end], vocal[start:end]
        for c in range(x.shape[1]):
            xx, vv = x[:, c].astype(np.float64), v[:, c].astype(np.float64)
            dot = float(np.dot(xx, vv))
            denx, denv = float(np.dot(xx, xx)), float(np.dot(vv, vv))
            corr = dot / (math.sqrt(denx * denv) + 1e-12)
            if abs(corr) < threshold or denv < 1e-10:
                continue
            alpha = max(-max_alpha, min(max_alpha, dot / (denv + 1e-12))) * strength
            n = end - start
            env = np.ones(n, dtype=np.float32)
            e = min(edge, n // 4)
            if e:
                ramp = np.linspace(0, 1, e, dtype=np.float32)
                env[:e] = ramp
                env[-e:] = ramp[::-1]
            out[start:end, c] = x[:, c] - alpha * v[:, c] * env
    return peak_normalize(out)
