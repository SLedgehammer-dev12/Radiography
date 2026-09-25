#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller entry point for the single-file Radiography Web launchers.

Double-click behaviour: a small control window (Tk, stdlib) opens together
with the default browser. "Tarayıcıda Aç" re-opens the browser; "Kapat" stops
the local server and exits. Launching the app again while it runs just opens
the browser without starting a second server.

Headless flags (used by CI smoke tests): ``--no-gui --no-browser --port 0``.
"""

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

from serve import (
    app_version,
    bundled_dir,
    is_running,
    resolve_dist,
    start_server,
)


def _open_browser(url: str) -> None:
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()


def _run_headless(server) -> int:
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _icon_paths():
    base = bundled_dir()
    ico = base / "RadiographyWeb.ico"
    png = base / "RadiographyWeb.png"
    return ico if ico.exists() else None, png if png.exists() else None


def _run_gui(server, url: str) -> int:
    import tkinter as tk
    from tkinter import ttk

    version = app_version()
    root = tk.Tk()
    root.title(f"Radiography Web {version}")
    root.geometry("380x180")
    root.resizable(False, False)
    root.configure(bg="#1b1f2e")

    ico, png = _icon_paths()
    try:
        if sys.platform == "win32" and ico:
            root.iconbitmap(default=str(ico))
        elif png:
            root.iconphoto(True, tk.PhotoImage(file=str(png)))
    except Exception:
        pass

    def on_open():
        webbrowser.open(url)

    def on_close():
        try:
            server.shutdown()
        finally:
            root.destroy()

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    frame = tk.Frame(root, bg="#1b1f2e", padx=18, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame, text="Radiography Web", fg="#e6e9f5", bg="#1b1f2e",
        font=("Helvetica", 14, "bold"),
    ).pack(anchor="w")
    tk.Label(
        frame, text=f"Surum / Version {version}", fg="#98a0bd", bg="#1b1f2e",
        font=("Helvetica", 10),
    ).pack(anchor="w")
    tk.Label(
        frame, text=url, fg="#7aa2ff", bg="#1b1f2e", font=("Helvetica", 10),
    ).pack(anchor="w", pady=(6, 12))

    buttons = tk.Frame(frame, bg="#1b1f2e")
    buttons.pack(anchor="e")
    tk.Button(
        buttons, text="Tarayıcıda Aç", command=on_open,
        bg="#7aa2ff", fg="#0f1117", relief="flat", padx=12, pady=5,
        font=("Helvetica", 11, "bold"), cursor="hand2",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        buttons, text="Kapat", command=on_close,
        bg="#2b3145", fg="#e6e9f5", relief="flat", padx=12, pady=5,
        font=("Helvetica", 11), cursor="hand2",
    ).pack(side="left")

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.lift()
    root.attributes("-topmost", True)
    root.after(1200, lambda: root.attributes("-topmost", False))
    root.mainloop()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Radiography Web")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--directory", default=None)
    args = parser.parse_args(argv)

    directory = Path(args.directory).resolve() if args.directory else resolve_dist()
    if not (directory / "index.html").exists():
        if not args.no_gui:
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "Radiography Web",
                    "Uygulama dosyalari bulunamadi (dist/index.html yok).",
                )
                root.destroy()
            except Exception:
                pass
        return 1

    if is_running(args.port):
        url = f"http://127.0.0.1:{args.port}/"
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    server, url, already = start_server(directory, args.port)
    if already or server is None:
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    if not args.no_browser:
        _open_browser(url)

    if args.no_gui:
        try:
            while thread.is_alive():
                thread.join(timeout=0.5)
        except KeyboardInterrupt:
            server.shutdown()
        finally:
            server.server_close()
        return 0

    try:
        return _run_gui(server, url)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
