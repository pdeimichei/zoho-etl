"""Zoho ETL – main entry point and Tkinter GUI."""

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Ensure src/ is on the path when running as a script or packaged executable
sys.path.insert(0, str(Path(__file__).parent))

from config import AppConfig
from email_sender import send_summary_email
from transform.listino_builder import build_listino
from transform.quote_processor import process_quotes

from _version import __version__
APP_TITLE = f"Zoho ETL  v{__version__}"


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, cfg: AppConfig):
        super().__init__(parent)
        self.cfg = cfg
        self.title("Settings")
        self.resizable(False, False)
        self.grab_set()  # modal

        pad = {"padx": 8, "pady": 4}

        # --- Working folder ---
        frm_folder = ttk.LabelFrame(self, text="Working Folder", padding=8)
        frm_folder.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 4))

        self._folder_var = tk.StringVar(value=cfg.working_folder)
        ttk.Entry(frm_folder, textvariable=self._folder_var, width=50).grid(row=0, column=0, sticky="ew")
        ttk.Button(frm_folder, text="Browse…", command=self._browse_folder).grid(row=0, column=1, padx=(6, 0))
        frm_folder.columnconfigure(0, weight=1)

        # --- File names ---
        frm_files = ttk.LabelFrame(self, text="Input / Output File Names", padding=8)
        frm_files.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        file_fields = [
            ("CRM export (quotes):", "input_quotes"),
            ("Price list file:    ", "input_listino"),
            ("Gadget / FOC file:  ", "input_gadget"),
            ("Customer file:      ", "input_clienti"),
            ("Output file:        ", "output_file"),
        ]
        self._file_vars: dict[str, tk.StringVar] = {}
        for i, (label, key) in enumerate(file_fields):
            ttk.Label(frm_files, text=label).grid(row=i, column=0, sticky="w", **pad)
            var = tk.StringVar(value=cfg.get_file(key))
            self._file_vars[key] = var
            ttk.Entry(frm_files, textvariable=var, width=30).grid(row=i, column=1, sticky="ew", **pad)
        frm_files.columnconfigure(1, weight=1)

        # --- Email / Azure AD ---
        frm_email = ttk.LabelFrame(self, text="Email (Microsoft Graph API)", padding=8)
        frm_email.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        azure_fields = [
            ("Tenant ID:",     "tenant_id",     False),
            ("Client ID:",     "client_id",     False),
            ("Client Secret:", "client_secret", True),
            ("From address:",  "from_address",  False),
        ]
        self._smtp_vars: dict[str, tk.StringVar] = {}
        for i, (label, attr, secret) in enumerate(azure_fields):
            ttk.Label(frm_email, text=label).grid(row=i, column=0, sticky="w", **pad)
            var = tk.StringVar(value=str(getattr(cfg, attr)))
            self._smtp_vars[attr] = var
            show = "*" if secret else ""
            ttk.Entry(frm_email, textvariable=var, width=36, show=show).grid(row=i, column=1, sticky="ew", **pad)

        frm_email.columnconfigure(1, weight=1)

        # Recipients
        frm_recip = ttk.LabelFrame(self, text="Email Recipients (one per line)", padding=8)
        frm_recip.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        self._recip_text = tk.Text(frm_recip, height=4, width=50)
        self._recip_text.grid(row=0, column=0, sticky="ew")
        self._recip_text.insert("1.0", "\n".join(cfg.recipients))
        frm_recip.columnconfigure(0, weight=1)

        # Subject prefix
        frm_subj = ttk.Frame(self, padding=(12, 0))
        frm_subj.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Label(frm_subj, text="Email subject prefix:").grid(row=0, column=0, sticky="w", **pad)
        self._subj_var = tk.StringVar(value=cfg.subject_prefix)
        ttk.Entry(frm_subj, textvariable=self._subj_var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        frm_subj.columnconfigure(1, weight=1)

        # --- Buttons ---
        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(frm_btn, text="Save", command=self._save).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self.columnconfigure(0, weight=1)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select working folder")
        if folder:
            self._folder_var.set(folder)

    def _save(self):
        self.cfg.working_folder = self._folder_var.get().strip()
        for key, var in self._file_vars.items():
            self.cfg.set_file(key, var.get().strip())
        self.cfg.tenant_id = self._smtp_vars["tenant_id"].get().strip()
        self.cfg.client_id = self._smtp_vars["client_id"].get().strip()
        self.cfg.client_secret = self._smtp_vars["client_secret"].get().strip()
        self.cfg.from_address = self._smtp_vars["from_address"].get().strip()
        raw_recip = self._recip_text.get("1.0", "end").strip()
        self.cfg.recipients = [r.strip() for r in raw_recip.splitlines() if r.strip()]
        self.cfg.subject_prefix = self._subj_var.get().strip()
        self.cfg.save()
        self.destroy()


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(True, True)
        self.minsize(560, 440)

        self.cfg = AppConfig()
        self.cfg.load()

        self._queue: queue.Queue = queue.Queue()
        self._running = False

        self._build_ui()
        self._update_folder_label()

        # Show settings on first run
        if self.cfg.needs_setup():
            self.after(200, lambda: SettingsDialog(self, self.cfg))

        self.after(100, self._poll_queue)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        pad = {"padx": 12, "pady": 6}

        # Top bar: folder + settings button
        frm_top = ttk.Frame(self)
        frm_top.grid(row=0, column=0, sticky="ew", **pad)
        frm_top.columnconfigure(1, weight=1)

        ttk.Label(frm_top, text="Folder:").grid(row=0, column=0, sticky="w")
        self._folder_lbl = ttk.Label(frm_top, text="", foreground="#555", anchor="w")
        self._folder_lbl.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Button(frm_top, text="Change…", command=self._pick_folder).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(frm_top, text="⚙ Settings", command=self._open_settings).grid(row=0, column=3, padx=(4, 0))

        # Run button + progress
        frm_run = ttk.Frame(self)
        frm_run.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 6))
        frm_run.columnconfigure(1, weight=1)

        self._run_btn = ttk.Button(frm_run, text="▶  Run ETL", command=self._start_pipeline, width=18)
        self._run_btn.grid(row=0, column=0)

        self._progress = ttk.Progressbar(frm_run, mode="determinate", maximum=100)
        self._progress.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        self._status_lbl = ttk.Label(frm_run, text="Ready.", anchor="w")
        self._status_lbl.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        # Log area
        frm_log = ttk.LabelFrame(self, text="Log", padding=6)
        frm_log.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        frm_log.columnconfigure(0, weight=1)
        frm_log.rowconfigure(0, weight=1)

        self._log = scrolledtext.ScrolledText(
            frm_log, state="disabled", wrap="word", height=16,
            font=("Courier New", 10) if sys.platform == "win32" else ("Menlo", 10),
        )
        self._log.grid(row=0, column=0, sticky="nsew")

        # Tag colours for log messages
        self._log.tag_config("ok", foreground="#2a9d2a")
        self._log.tag_config("warn", foreground="#c77a00")
        self._log.tag_config("error", foreground="#c0392b")
        self._log.tag_config("info", foreground="#222")

    # -----------------------------------------------------------------------
    # Folder helpers
    # -----------------------------------------------------------------------

    def _update_folder_label(self):
        folder = self.cfg.working_folder or "(not set)"
        self._folder_lbl.config(text=folder)

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select working folder")
        if folder:
            self.cfg.working_folder = folder
            self.cfg.save()
            self._update_folder_label()

    def _open_settings(self):
        dlg = SettingsDialog(self, self.cfg)
        self.wait_window(dlg)
        self._update_folder_label()

    # -----------------------------------------------------------------------
    # Logging helpers (thread-safe via queue)
    # -----------------------------------------------------------------------

    def _log_append(self, text: str, tag: str = "info"):
        self._log.config(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    # -----------------------------------------------------------------------
    # Queue polling (bridges worker thread → UI thread)
    # -----------------------------------------------------------------------

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg.get("kind")

                if kind == "log":
                    self._log_append(msg["text"], msg.get("tag", "info"))
                elif kind == "progress":
                    self._progress["value"] = msg["value"]
                elif kind == "status":
                    self._status_lbl.config(text=msg["text"])
                elif kind == "done":
                    self._running = False
                    self._run_btn.config(state="normal")
                    if msg.get("success"):
                        self._progress["value"] = 100
                        self._status_lbl.config(text="Done.")
                    else:
                        self._status_lbl.config(text="Failed — see log above.")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    # -----------------------------------------------------------------------
    # Pipeline runner
    # -----------------------------------------------------------------------

    def _start_pipeline(self):
        errors = self.cfg.validate()
        if errors:
            messagebox.showerror("Configuration error", "\n".join(errors))
            return

        self._clear_log()
        self._progress["value"] = 0
        self._run_btn.config(state="disabled")
        self._running = True

        t = threading.Thread(target=self._run_pipeline, daemon=True)
        t.start()

    def _run_pipeline(self):
        q = self._queue
        cfg = self.cfg

        def log(text, tag="info"):
            q.put({"kind": "log", "text": text, "tag": tag})

        def progress(pct):
            q.put({"kind": "progress", "value": pct})

        def status(text):
            q.put({"kind": "status", "text": text})

        try:
            # --- Stage 1 ---
            status("Stage 1: building price list…")
            log("Reading input files…")

            export_path   = cfg.get_input_path("input_quotes")
            listino09_path = cfg.get_input_path("input_listino")
            gadget_path   = cfg.get_input_path("input_gadget")
            clienti_path  = cfg.get_input_path("input_clienti")
            output_path   = cfg.get_output_path()

            for p in (export_path, listino09_path, gadget_path, clienti_path):
                if not p.exists():
                    raise FileNotFoundError(f"Input file not found: {p}")

            listino_df = build_listino(export_path, listino09_path, gadget_path, clienti_path)
            log(f"✓ Price list built: {len(listino_df)} rows", "ok")
            progress(35)

            # --- Stage 2 ---
            status("Stage 2: processing quotes…")
            _, email_body = process_quotes(export_path, listino_df, output_path)

            log(f"✓ {output_path.name} written to {output_path.parent}", "ok")
            progress(70)

            # --- Email ---
            if cfg.email_configured:
                status("Sending email…")
                log(f"Sending summary to: {', '.join(cfg.recipients)}")
                send_summary_email(cfg, email_body)
                log("✓ Email sent.", "ok")
            else:
                log("⚠ Email skipped — Azure AD credentials not configured (set them in Settings).", "warn")
            progress(100)

            q.put({"kind": "done", "success": True})

        except Exception as exc:
            log(f"ERROR: {exc}", "error")
            q.put({"kind": "done", "success": False})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = App()
    app.mainloop()
