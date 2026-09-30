"""Tampilan desktop sederhana untuk Local Denoise."""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from denoise_cli import __version__
from denoise_cli.core import (
    AUDIO_EXTENSIONS,
    PRESETS,
    VIDEO_EXTENSIONS,
    DenoiseError,
    default_output_path,
    media_kind,
    probe_media,
    process_media,
    resolve_ffmpeg,
)


def _patterns(extensions: set[str]) -> str:
    return " ".join(f"*{ext}" for ext in sorted(extensions))


MEDIA_FILETYPES = [
    ("Audio dan video", _patterns(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS)),
    ("Video", _patterns(VIDEO_EXTENSIONS)),
    ("Audio", _patterns(AUDIO_EXTENSIONS)),
    ("Semua file", "*.*"),
]

PRESET_LABELS = {
    "light": "Ringan - jaga detail musik",
    "balanced": "Seimbang - ucapan dan umum",
    "strong": "Kuat - noise yang jelas",
}


class DenoiseApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.events: queue.Queue[tuple] = queue.Queue()
        self.cancel_event: threading.Event | None = None
        self.probe_id = 0
        self.last_output: Path | None = None

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.engine_var = tk.StringVar(value="spectral")
        self.preset_var = tk.StringVar(value=PRESET_LABELS["balanced"])
        self.model_var = tk.StringVar(value=os.environ.get("DENOISE_RNNOISE_MODEL", ""))
        self.status_var = tk.StringVar(value="Pilih file audio atau video untuk mulai.")
        self.track_vars: list[tk.BooleanVar] = []

        self._build()
        self._update_engine_state()
        self._poll_id = self.after(100, self._poll_events)

    def destroy(self) -> None:
        self.after_cancel(self._poll_id)
        if self.cancel_event is not None:
            self.cancel_event.set()
        super().destroy()

    # ---------- tata letak ----------

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="File input").grid(row=0, column=0, sticky="w", pady=4)
        self.input_entry = ttk.Entry(self, textvariable=self.input_var, state="readonly")
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=8)
        self.input_button = ttk.Button(self, text="Pilih...", command=self._choose_input)
        self.input_button.grid(row=0, column=2, sticky="ew")

        ttk.Label(self, text="Simpan ke").grid(row=1, column=0, sticky="w", pady=4)
        self.output_entry = ttk.Entry(self, textvariable=self.output_var)
        self.output_entry.grid(row=1, column=1, sticky="ew", padx=8)
        self.output_button = ttk.Button(self, text="Ubah...", command=self._choose_output)
        self.output_button.grid(row=1, column=2, sticky="ew")

        settings = ttk.LabelFrame(self, text="Pengaturan", padding=12)
        settings.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Metode").grid(row=0, column=0, sticky="w", pady=4)
        engines = ttk.Frame(settings)
        engines.grid(row=0, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Radiobutton(
            engines,
            text="Spectral (cepat, noise stabil)",
            value="spectral",
            variable=self.engine_var,
            command=self._update_engine_state,
        ).pack(side="left")
        ttk.Radiobutton(
            engines,
            text="RNNoise (neural, khusus ucapan)",
            value="rnnoise",
            variable=self.engine_var,
            command=self._update_engine_state,
        ).pack(side="left", padx=(16, 0))

        ttk.Label(settings, text="Kekuatan").grid(row=1, column=0, sticky="w", pady=4)
        self.preset_box = ttk.Combobox(
            settings,
            textvariable=self.preset_var,
            values=[PRESET_LABELS[name] for name in PRESETS],
            state="readonly",
        )
        self.preset_box.grid(row=1, column=1, columnspan=2, sticky="ew", padx=8)

        ttk.Label(settings, text="Model RNNoise").grid(row=2, column=0, sticky="w", pady=4)
        self.model_entry = ttk.Entry(settings, textvariable=self.model_var)
        self.model_entry.grid(row=2, column=1, sticky="ew", padx=8)
        self.model_button = ttk.Button(settings, text="Pilih...", command=self._choose_model)
        self.model_button.grid(row=2, column=2, sticky="ew")

        self.tracks_frame = ttk.LabelFrame(self, text="Track audio", padding=12)
        self.tracks_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._show_track_message("Belum ada file yang dipilih.")

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(16, 4))
        self.status_label = ttk.Label(
            self, textvariable=self.status_var, wraplength=520, justify="left"
        )
        self.status_label.grid(row=5, column=0, columnspan=3, sticky="w")

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e", pady=(16, 0))
        self.open_button = ttk.Button(
            buttons, text="Buka folder hasil", command=self._open_output_folder
        )
        self.cancel_button = ttk.Button(buttons, text="Batal", command=self._cancel)
        self.run_button = ttk.Button(buttons, text="Proses", command=self._start)
        self.run_button.pack(side="right")

    def _show_track_message(self, text: str) -> None:
        for child in self.tracks_frame.winfo_children():
            child.destroy()
        self.track_vars = []
        ttk.Label(self.tracks_frame, text=text).pack(anchor="w")

    def _show_tracks(self, tracks: tuple[str, ...], kind: str) -> None:
        for child in self.tracks_frame.winfo_children():
            child.destroy()
        self.track_vars = []
        if not tracks:
            ttk.Label(
                self.tracks_frame, text="File ini tidak memiliki track audio."
            ).pack(anchor="w")
            return
        for number, description in enumerate(tracks, start=1):
            # Video: semua track diproses; audio: hanya satu track yang dapat disimpan.
            var = tk.BooleanVar(value=kind == "video" or number == 1)
            self.track_vars.append(var)
            ttk.Checkbutton(
                self.tracks_frame,
                text=f"Track {number}: {description}",
                variable=var,
            ).pack(anchor="w")

    def _scroll_paths_to_end(self) -> None:
        # Tampilkan ujung path agar nama file tetap terlihat pada path panjang.
        for entry in (self.input_entry, self.output_entry):
            entry.xview_moveto(1.0)

    def _update_engine_state(self) -> None:
        spectral = self.engine_var.get() == "spectral"
        self.preset_box.configure(state="readonly" if spectral else "disabled")
        model_state = "disabled" if spectral else "normal"
        self.model_entry.configure(state=model_state)
        self.model_button.configure(state=model_state)

    # ---------- aksi pengguna ----------

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.master, title="Pilih file audio atau video", filetypes=MEDIA_FILETYPES
        )
        if filename:
            self.set_input(Path(filename))

    def set_input(self, path: Path) -> None:
        self.input_var.set(str(path))
        self.output_var.set(str(default_output_path(path)))
        self._scroll_paths_to_end()
        self.progress.configure(value=0)
        self.open_button.pack_forget()
        try:
            kind = media_kind(path)
        except DenoiseError as exc:
            self._show_track_message("-")
            self._set_status(str(exc), error=True)
            return

        self.probe_id += 1
        probe_id = self.probe_id
        self._show_track_message("Membaca informasi file...")
        self._set_status("Membaca informasi file...")

        def worker() -> None:
            try:
                info = probe_media(resolve_ffmpeg(), path)
                self.events.put(("probed", probe_id, info.audio_tracks, kind))
            except DenoiseError as exc:
                self.events.put(("probe_error", probe_id, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _choose_output(self) -> None:
        current = Path(self.output_var.get()) if self.output_var.get() else None
        suffix = current.suffix if current else ""
        filename = filedialog.asksaveasfilename(
            parent=self.master,
            title="Simpan hasil sebagai",
            initialdir=str(current.parent) if current else None,
            initialfile=current.name if current else None,
            defaultextension=suffix,
            filetypes=[(f"File {suffix}", f"*{suffix}")] if suffix else MEDIA_FILETYPES,
            confirmoverwrite=False,
        )
        if filename:
            self.output_var.set(filename)
            self._scroll_paths_to_end()

    def _choose_model(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.master,
            title="Pilih model RNNoise",
            filetypes=[("Model RNNoise", "*.rnnn"), ("Semua file", "*.*")],
        )
        if filename:
            self.model_var.set(filename)

    def selected_preset(self) -> str:
        label = self.preset_var.get()
        for name, preset_label in PRESET_LABELS.items():
            if preset_label == label:
                return name
        return "balanced"

    def selected_tracks(self) -> list[int]:
        return [number for number, var in enumerate(self.track_vars, start=1) if var.get()]

    def _start(self) -> None:
        if not self.input_var.get():
            self._set_status("Pilih file input terlebih dahulu.", error=True)
            return
        if not self.output_var.get().strip():
            self._set_status("Tentukan lokasi file hasil.", error=True)
            return
        if not self.track_vars:
            self._set_status("Tidak ada track audio yang dapat diproses.", error=True)
            return
        tracks = self.selected_tracks()
        if not tracks:
            self._set_status("Centang minimal satu track audio.", error=True)
            return

        input_path = Path(self.input_var.get())
        output_path = Path(self.output_var.get().strip())
        force = False
        if output_path.exists():
            force = messagebox.askyesno(
                "File sudah ada",
                f"{output_path.name} sudah ada.\nTimpa file tersebut?",
                parent=self.master,
            )
            if not force:
                return

        options = dict(
            input_path=input_path,
            output_path=output_path,
            preset_name=self.selected_preset(),
            force=force,
            engine=self.engine_var.get(),
            model_path=self.model_var.get().strip() or None,
            tracks=tracks,
        )
        self.cancel_event = threading.Event()
        self._set_running(True)
        self.progress.configure(value=0)
        self._set_status("Memproses...")

        def worker(cancel: threading.Event) -> None:
            try:
                process_media(
                    **options,
                    on_progress=lambda fraction: self.events.put(("progress", fraction)),
                    cancel=cancel,
                )
                self.events.put(("done", output_path))
            except DenoiseError as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:  # jangan biarkan thread mati tanpa kabar
                self.events.put(("error", f"Kesalahan tak terduga: {exc}"))

        threading.Thread(target=worker, args=(self.cancel_event,), daemon=True).start()

    def _cancel(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()
            self._set_status("Membatalkan...")

    def _open_output_folder(self) -> None:
        if self.last_output is None:
            return
        folder = self.last_output.parent
        try:
            if sys.platform == "win32":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.spawnlp(os.P_NOWAIT, "open", "open", str(folder))
            else:
                os.spawnlp(os.P_NOWAIT, "xdg-open", "xdg-open", str(folder))
        except OSError as exc:
            self._set_status(f"Tidak dapat membuka folder: {exc}", error=True)

    # ---------- status dan event dari thread ----------

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_var.set(text)
        self.status_label.configure(foreground="#b00020" if error else "")

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for widget in (self.input_button, self.output_button, self.run_button):
            widget.configure(state=state)
        if running:
            self.open_button.pack_forget()
            self.cancel_button.pack(side="right", padx=(0, 8))
        else:
            self.cancel_button.pack_forget()
            self.cancel_event = None

    def _poll_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll_events)

    def _handle_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "probed":
            _, probe_id, tracks, media_type = event
            if probe_id != self.probe_id:
                return
            self._show_tracks(tracks, media_type)
            if tracks:
                self._set_status("Siap diproses. Tekan Proses untuk mulai.")
            else:
                self._set_status("File ini tidak memiliki track audio.", error=True)
        elif kind == "probe_error":
            _, probe_id, message = event
            if probe_id == self.probe_id:
                self._show_track_message("-")
                self._set_status(message, error=True)
        elif kind == "progress":
            percent = event[1] * 100
            self.progress.configure(value=percent)
            self._set_status(f"Memproses... {percent:.0f}%")
        elif kind == "done":
            self.last_output = Path(event[1]).expanduser().resolve()
            self.progress.configure(value=100)
            self._set_running(False)
            self._set_status(f"Selesai: {self.last_output.name}")
            self.open_button.pack(side="right", padx=(0, 8))
        elif kind == "error":
            self._set_running(False)
            self.progress.configure(value=0)
            self._set_status(event[1], error=True)


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main() -> int:
    _enable_dpi_awareness()
    root = tk.Tk()
    root.title(f"Local Denoise {__version__}")
    root.minsize(600, 0)
    app = DenoiseApp(root)
    app.pack(fill="both", expand=True)
    if len(sys.argv) > 1:
        app.set_input(Path(sys.argv[1]))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
