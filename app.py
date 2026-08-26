from __future__ import annotations

# Defense-in-depth for PyInstaller --windowed builds.
import os as _stdio_os
import sys as _stdio_sys
_STDIO_KEEP=[]
def _ensure_stdio():
    for _name,_mode in (("stdout","w"),("stderr","w"),("stdin","r")):
        if getattr(_stdio_sys,_name) is None:
            _f=open(_stdio_os.devnull,_mode,buffering=1 if "w" in _mode else -1,encoding="utf-8",errors="replace")
            _STDIO_KEEP.append(_f)
            setattr(_stdio_sys,_name,_f)
_ensure_stdio()

import os
import sys
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QProgressBar, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QDoubleSpinBox,
    QMessageBox, QTabWidget, QGroupBox, QCheckBox, QLineEdit
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from engine import StemEngine


APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PROJECTS_DIR = None


class ModelDownloadThread(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        try:
            result = self.engine.download_models(
                progress=lambda p, m: self.progress.emit(int(p), str(m))
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class ExtractThread(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, engine, source, out_dir, mode, cleanup):
        super().__init__()
        self.engine = engine
        self.source = source
        self.out_dir = out_dir
        self.mode = mode
        self.cleanup = cleanup

    def run(self):
        try:
            result = self.engine.separate(
                self.source, self.out_dir,
                mode=self.mode, cleanup=self.cleanup,
                progress=lambda p, m: self.progress.emit(int(p), str(m)),
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class AudioDNAStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio DNA Studio Pro — Offline Desktop")
        self.resize(1320, 860)

        self.engine = StemEngine(APP_DIR)
        global PROJECTS_DIR
        PROJECTS_DIR = self.engine.projects_dir
        self.source_file = None
        self.project_dir = None
        self.stems = {}
        self.active_stem = None

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.9)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)

        self.selection_timer = QTimer(self)
        self.selection_timer.setInterval(50)
        self.selection_timer.timeout.connect(self._enforce_selection_end)

        self._build_ui()
        self._refresh_system_status()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        title = QLabel("Audio DNA Studio Pro — Offline Desktop")
        title.setStyleSheet("font-size:24px;font-weight:800;")
        subtitle = QLabel(
            "No extraction API • No server • Direct local BS‑RoFormer + Demucs inference • "
            "Vocals / Drums / Bass / Guitar / Piano / Other / Instrumental"
        )
        subtitle.setStyleSheet("color:#6d7890;")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        source_box = QGroupBox("1. Source and Extraction")
        grid = QGridLayout(source_box)
        self.source_label = QLineEdit()
        self.source_label.setReadOnly(True)
        self.source_label.setPlaceholderText("Choose a song…")
        browse = QPushButton("Choose Audio")
        browse.clicked.connect(self.choose_audio)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Maximum Accuracy — BS‑RoFormer + Demucs Ensemble", "maximum")
        self.mode_combo.addItem("BS‑RoFormer 6‑Stem", "roformer")
        self.mode_combo.addItem("Demucs htdemucs_ft 4‑Stem", "demucs")

        self.cleanup_combo = QComboBox()
        self.cleanup_combo.addItem("Strong vocal-bleed cleanup", "strong")
        self.cleanup_combo.addItem("Conservative cleanup", "conservative")
        self.cleanup_combo.addItem("Aggressive cleanup", "aggressive")

        self.extract_btn = QPushButton("Extract Stems")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self.extract_stems)

        grid.addWidget(QLabel("Audio:"), 0, 0)
        grid.addWidget(self.source_label, 0, 1, 1, 3)
        grid.addWidget(browse, 0, 4)
        grid.addWidget(QLabel("Engine:"), 1, 0)
        grid.addWidget(self.mode_combo, 1, 1, 1, 2)
        grid.addWidget(QLabel("Cleanup:"), 1, 3)
        grid.addWidget(self.cleanup_combo, 1, 4)
        grid.addWidget(self.extract_btn, 2, 4)
        outer.addWidget(source_box)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        # Stems / timeline
        stems_tab = QWidget()
        stems_layout = QVBoxLayout(stems_tab)

        transport = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.pause_btn = QPushButton("⏸ Pause")
        self.stop_btn = QPushButton("■ Stop")
        self.back_btn = QPushButton("◀ 5s")
        self.forward_btn = QPushButton("5s ▶")
        self.play_sel_btn = QPushButton("▶ Play Selection")
        self.play_btn.clicked.connect(self.play_active)
        self.pause_btn.clicked.connect(self.player.pause)
        self.stop_btn.clicked.connect(self.stop_playback)
        self.back_btn.clicked.connect(lambda: self.seek_relative(-5000))
        self.forward_btn.clicked.connect(lambda: self.seek_relative(5000))
        self.play_sel_btn.clicked.connect(self.play_selection)
        for b in [self.play_btn, self.pause_btn, self.stop_btn, self.back_btn, self.forward_btn, self.play_sel_btn]:
            b.setEnabled(False)
            transport.addWidget(b)
        transport.addStretch()
        self.time_label = QLabel("00:00.000 / 00:00.000")
        transport.addWidget(self.time_label)
        stems_layout.addLayout(transport)

        self.timeline = QSlider(Qt.Horizontal)
        self.timeline.setRange(0, 1000)
        self.timeline.setEnabled(False)
        self.timeline.sliderMoved.connect(self._slider_seek)
        stems_layout.addWidget(self.timeline)

        sel = QHBoxLayout()
        self.sel_start = QDoubleSpinBox()
        self.sel_end = QDoubleSpinBox()
        for box in (self.sel_start, self.sel_end):
            box.setDecimals(3)
            box.setRange(0, 999999)
        sel.addWidget(QLabel("Selection start (s)"))
        sel.addWidget(self.sel_start)
        sel.addWidget(QLabel("Selection end (s)"))
        sel.addWidget(self.sel_end)
        around = QPushButton("Set 5s Around Playhead")
        around.clicked.connect(self.set_selection_around_playhead)
        sel.addWidget(around)
        sel.addStretch()
        stems_layout.addLayout(sel)

        self.stem_table = QTableWidget(0, 7)
        self.stem_table.setHorizontalHeaderLabels(
            ["Stem", "Type", "Play", "Play Selection", "Stop", "Download WAV", "Use in Mix"]
        )
        self.stem_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        stems_layout.addWidget(self.stem_table, 1)

        self.render_mix_btn = QPushButton("Render Selected Stem Mix")
        self.render_mix_btn.setEnabled(False)
        self.render_mix_btn.clicked.connect(self.render_mix)
        stems_layout.addWidget(self.render_mix_btn)

        self.tabs.addTab(stems_tab, "Stems / Timeline")

        # Diagnostics
        diag = QWidget()
        diag_layout = QVBoxLayout(diag)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        diag_layout.addWidget(self.status_label)

        diag_actions = QHBoxLayout()
        refresh = QPushButton("Refresh System Check")
        refresh.clicked.connect(self._refresh_system_status)
        download_models = QPushButton("Download / Verify AI Models")
        download_models.clicked.connect(self.download_models)
        import_roformer = QPushButton("Import BS-RoFormer Checkpoint")
        import_roformer.clicked.connect(self.import_roformer_checkpoint)
        models = QPushButton("Open Models Folder")
        models.clicked.connect(self.open_models_folder)
        projects = QPushButton("Open Projects Folder")
        projects.clicked.connect(self.open_projects_folder)
        diag_actions.addWidget(refresh)
        diag_actions.addWidget(download_models)
        diag_actions.addWidget(import_roformer)
        diag_actions.addWidget(models)
        diag_actions.addWidget(projects)
        diag_actions.addStretch()
        diag_layout.addLayout(diag_actions)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        diag_layout.addWidget(self.log, 1)
        self.tabs.addTab(diag, "Diagnostics / Log")

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress_text = QLabel("Ready.")
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.progress_text)
        outer.addLayout(bottom)

        menu = self.menuBar().addMenu("File")
        open_action = QAction("Open Audio", self)
        open_action.triggered.connect(self.choose_audio)
        menu.addAction(open_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

    def choose_audio(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Choose audio", "",
            "Audio (*.wav *.mp3 *.m4a *.aac *.flac *.ogg);;All Files (*.*)"
        )
        if not file:
            return
        self.source_file = Path(file)
        self.source_label.setText(file)
        self.extract_btn.setEnabled(True)
        self.log.appendPlainText(f"Source: {file}")

    def _refresh_system_status(self):
        info = self.engine.system_info()
        lines = [
            f"Python: {info['python']}",
            f"FFmpeg: {'OK' if info['ffmpeg'] else 'MISSING'}",
            f"BS‑RoFormer engine: {'OK' if info['roformer'] else 'MISSING'}",
            f"BS‑RoFormer checkpoint: {'OK' if info.get('roformer_checkpoint') else 'MISSING / INVALID'}",
            f"Checkpoint path: {info.get('roformer_checkpoint_path','')}",
            f"Demucs: {'OK' if info['demucs'] else 'MISSING'}",
            f"PyTorch: {'OK' if info['torch'] else 'MISSING'}",
            f"CUDA GPU: {info['cuda_name'] if info['cuda'] else 'CPU mode / CUDA not detected'}",
            f"Models folder: {self.engine.models_dir}",
            "Stem inference: DIRECT LOCAL MODEL EXECUTION.",
        ]
        self.status_label.setText("\n".join(lines))
        self.log.appendPlainText("\n".join(lines) + "\n")

    def import_roformer_checkpoint(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select BS-RoFormer Checkpoint", "", "BS-RoFormer Checkpoint (*.ckpt);;All Files (*.*)")
        if not file: return
        try:
            self.progress.setValue(10)
            self.progress_text.setText("Verifying checkpoint SHA-256…")
            result = self.engine.import_roformer_checkpoint(Path(file))
            self.progress.setValue(100)
            self.progress_text.setText("BS-RoFormer checkpoint verified.")
            self.log.appendPlainText("Imported BS-RoFormer checkpoint:\n" + result.get("path", "") + "\nSHA-256: " + result.get("sha256", ""))
            self._refresh_system_status()
            QMessageBox.information(self, "Checkpoint ready", "BS-RoFormer checkpoint was SHA-256 verified and installed locally.")
        except Exception as exc:
            self.progress_text.setText("Checkpoint import failed.")
            QMessageBox.critical(self, "Checkpoint import failed", str(exc))

    def download_models(self):
        self.progress.setValue(0)
        self.progress_text.setText("Preparing model download…")
        self.model_worker = ModelDownloadThread(self.engine)
        self.model_worker.progress.connect(self._extract_progress)
        self.model_worker.finished_ok.connect(self._models_done)
        self.model_worker.failed.connect(self._models_failed)
        self.model_worker.start()

    def _models_done(self, result):
        self.progress.setValue(100)
        self.progress_text.setText("Models ready for offline use.")
        self.log.appendPlainText("Model files verified in: " + str(self.engine.models_dir))
        self._refresh_system_status()
        QMessageBox.information(
            self, "Models ready",
            "BS‑RoFormer and Demucs model files are cached locally. "
            "Stem extraction can now run without an internet connection."
        )

    def _models_failed(self, message):
        self.progress_text.setText("Model setup failed.")
        self.log.appendPlainText("MODEL ERROR: " + message)
        QMessageBox.critical(self, "Model setup failed", message)

    def extract_stems(self):
        if not self.source_file:
            return
        mode = self.mode_combo.currentData()
        cleanup = self.cleanup_combo.currentData()
        info = self.engine.system_info()

        if not info["ffmpeg"]:
            QMessageBox.critical(self, "Missing FFmpeg", "FFmpeg is required. See README.txt.")
            return
        if mode in ("maximum", "roformer") and not info["roformer"]:
            QMessageBox.critical(self, "BS‑RoFormer engine unavailable", "This build cannot import the BS-RoFormer engine.")
            return
        if mode in ("maximum", "roformer") and not info.get("roformer_checkpoint"):
            QMessageBox.critical(self, "BS‑RoFormer checkpoint missing", "Open Diagnostics / Log and click Download / Verify AI Models. If automatic download fails, download BS-Rofo-SW-Fixed.ckpt in your browser and click Import BS-RoFormer Checkpoint.")
            return
        if mode in ("maximum", "demucs") and not info["demucs"]:
            QMessageBox.critical(self, "Demucs unavailable", "Open Diagnostics / Log and click Download / Verify AI Models.")
            return

        self.project_dir = PROJECTS_DIR / self.source_file.stem
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.extract_btn.setEnabled(False)
        self.progress.setValue(0)

        self.worker = ExtractThread(
            self.engine, self.source_file, self.project_dir, mode, cleanup
        )
        self.worker.progress.connect(self._extract_progress)
        self.worker.finished_ok.connect(self._extract_done)
        self.worker.failed.connect(self._extract_failed)
        self.worker.start()

    def _extract_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.progress_text.setText(msg)
        self.log.appendPlainText(msg)

    def _extract_done(self, result):
        self.extract_btn.setEnabled(True)
        self.progress.setValue(100)
        self.progress_text.setText("Extraction complete.")
        self.stems = {k: Path(v) for k, v in result["stems"].items()}
        self.log.appendPlainText("Engine: " + result.get("engine", ""))
        if result.get("qc"):
            import json
            self.log.appendPlainText("QC:\n" + json.dumps(result["qc"], indent=2))
        self.populate_stems()
        QMessageBox.information(self, "Done", "Local stem extraction completed.")

    def _extract_failed(self, message):
        self.extract_btn.setEnabled(True)
        self.progress_text.setText("Extraction failed.")
        self.log.appendPlainText("ERROR: " + message)
        QMessageBox.critical(self, "Extraction failed", message)

    def populate_stems(self):
        order = ["vocals", "drums", "bass", "guitar", "piano", "other", "instrumental"]
        rows = [(k, self.stems[k]) for k in order if k in self.stems]
        self.stem_table.setRowCount(len(rows))

        for row, (name, path) in enumerate(rows):
            self.stem_table.setItem(row, 0, QTableWidgetItem(name.title()))
            self.stem_table.setItem(row, 1, QTableWidgetItem("Local neural stem"))

            play = QPushButton("▶")
            play.clicked.connect(lambda _=False, n=name: self.play_stem(n, False))
            play_sel = QPushButton("▶ Selection")
            play_sel.clicked.connect(lambda _=False, n=name: self.play_stem(n, True))
            stop = QPushButton("■")
            stop.clicked.connect(self.stop_playback)
            dl = QPushButton("Download")
            dl.clicked.connect(lambda _=False, n=name: self.download_stem(n))
            mix = QCheckBox()
            mix.setChecked(name not in ("vocals", "instrumental"))
            holder = QWidget()
            h = QHBoxLayout(holder)
            h.setContentsMargins(0, 0, 0, 0)
            h.setAlignment(Qt.AlignCenter)
            h.addWidget(mix)

            self.stem_table.setCellWidget(row, 2, play)
            self.stem_table.setCellWidget(row, 3, play_sel)
            self.stem_table.setCellWidget(row, 4, stop)
            self.stem_table.setCellWidget(row, 5, dl)
            self.stem_table.setCellWidget(row, 6, holder)

        for b in [self.play_btn, self.pause_btn, self.stop_btn, self.back_btn, self.forward_btn, self.play_sel_btn]:
            b.setEnabled(bool(rows))
        self.timeline.setEnabled(bool(rows))
        self.render_mix_btn.setEnabled(bool(rows))

        if rows:
            self.active_stem = rows[0][0]
            self.set_media(rows[0][1])

    def set_media(self, path):
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        self.timeline.setValue(0)

    def play_stem(self, name, selection=False):
        path = self.stems.get(name)
        if not path:
            return
        self.active_stem = name
        self.set_media(path)
        if selection:
            self.player.setPosition(int(self.sel_start.value() * 1000))
            self.selection_timer.start()
        else:
            self.selection_timer.stop()
        self.player.play()

    def play_active(self):
        if not self.active_stem:
            return
        self.selection_timer.stop()
        self.player.play()

    def play_selection(self):
        if not self.active_stem:
            return
        self.player.setPosition(int(self.sel_start.value() * 1000))
        self.selection_timer.start()
        self.player.play()

    def stop_playback(self):
        self.selection_timer.stop()
        self.player.stop()

    def _enforce_selection_end(self):
        end_ms = int(self.sel_end.value() * 1000)
        if end_ms > 0 and self.player.position() >= end_ms:
            self.player.pause()
            self.selection_timer.stop()

    def seek_relative(self, delta):
        self.player.setPosition(max(0, self.player.position() + delta))

    def _slider_seek(self, value):
        dur = self.player.duration()
        if dur > 0:
            self.player.setPosition(int(dur * value / 1000))

    def _position_changed(self, pos):
        dur = self.player.duration()
        if dur > 0 and not self.timeline.isSliderDown():
            self.timeline.setValue(int(pos / dur * 1000))
        self.time_label.setText(f"{format_ms(pos)} / {format_ms(dur)}")

    def _duration_changed(self, dur):
        seconds = max(0.0, dur / 1000)
        self.sel_start.setMaximum(seconds)
        self.sel_end.setMaximum(seconds)
        if self.sel_end.value() == 0:
            self.sel_end.setValue(min(10.0, seconds))

    def set_selection_around_playhead(self):
        sec = self.player.position() / 1000
        dur = self.player.duration() / 1000
        self.sel_start.setValue(max(0.0, sec - 2.5))
        self.sel_end.setValue(min(dur, sec + 2.5))

    def download_stem(self, name):
        src = self.stems.get(name)
        if not src:
            return
        default = Path.home() / f"{self.source_file.stem}_{name}.wav"
        dest, _ = QFileDialog.getSaveFileName(self, f"Save {name}", str(default), "WAV (*.wav)")
        if dest:
            shutil.copy2(src, dest)

    def render_mix(self):
        selected = []
        for row in range(self.stem_table.rowCount()):
            name = self.stem_table.item(row, 0).text().lower()
            holder = self.stem_table.cellWidget(row, 6)
            cb = holder.findChild(QCheckBox) if holder else None
            if cb and cb.isChecked() and name in self.stems:
                selected.append(self.stems[name])
        if not selected:
            QMessageBox.warning(self, "No stems selected", "Select at least one stem for the mix.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save mix", str(Path.home() / f"{self.source_file.stem}_custom_mix.wav"),
            "WAV (*.wav)"
        )
        if not dest:
            return
        try:
            self.engine.render_mix(selected, Path(dest))
            QMessageBox.information(self, "Done", "24-bit WAV mix created.")
        except Exception as exc:
            QMessageBox.critical(self, "Mix failed", str(exc))

    def open_models_folder(self):
        if os.name == "nt":
            os.startfile(self.engine.models_dir)

    def open_projects_folder(self):
        if os.name == "nt":
            os.startfile(PROJECTS_DIR)


def format_ms(ms):
    ms = max(0, int(ms or 0))
    mins = ms // 60000
    secs = (ms % 60000) / 1000
    return f"{mins:02d}:{secs:06.3f}"


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    _ensure_stdio()

    if "--self-check" in sys.argv:
        import json
        engine = StemEngine(APP_DIR)
        info = engine.system_info()
        print(json.dumps(info, indent=2))
        return 0 if info.get("ready") else 2
    app = QApplication(sys.argv)
    app.setApplicationName("Audio DNA Studio Pro")
    win = AudioDNAStudio()
    win.show()
    return app.exec()


if __name__ == "__main__":
    main()
