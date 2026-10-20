
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

import core

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:
    HAS_DND = False

try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None

APP_NAME = "Syntax Convert"
VERSION = "2.0"

THEMES = {
    "light": dict(bg="#f4f6fb", panel="#ffffff", fg="#1c2236", sub="#6b748c", accent="#635bff",
                  accent_h="#5148e5", border="#dde2ee", side="#ffffff", field="#ffffff", sel="#ecebff",
                  ok="#1a9d5b", err="#d64545"),
    "dark": dict(bg="#13151f", panel="#1c1f2e", fg="#e9ebf4", sub="#9aa3bb", accent="#7c75ff",
                 accent_h="#6b64f0", border="#2b3047", side="#181b28", field="#252a3e", sel="#2b2e57",
                 ok="#3ecf8e", err="#ff6b6b"),
}

PDF_T = [("PDF files", "*.pdf")]
IMG_T = [("Images", core.IMAGE_EXT), ("All files", "*.*")]

# (page name, icon, builder method)
PAGES = [
    ("Home", "🏠", "page_home"),
    ("Image Resize", "🖼", "page_resize"),
    ("Image Convert", "🔁", "page_convert"),
    ("PDF Tools", "📄", "page_pdf"),
    ("Office Convert", "📑", "page_office"),
    ("Utilities", "🧰", "page_utils"),
    ("Settings", "⚙", "page_settings"),
]


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ======================================================================
#  Reusable widget: list of files with add / remove / reorder / drag-drop
# ======================================================================
class FileList(ttk.Frame):
    def __init__(self, app, master, types, height=6, ordered=False, on_select=None):
        super().__init__(master, style="Card.TFrame")
        self.app, self.types, self.paths, self.on_select = app, types, [], on_select
        t = app.t
        self.lb = tk.Listbox(self, height=height, selectmode="extended", activestyle="none", bg=t["field"],
                             fg=t["fg"], selectbackground=t["accent"], selectforeground="white", relief="flat",
                             highlightthickness=1, highlightbackground=t["border"], highlightcolor=t["accent"],
                             font=app.font)
        self.lb.pack(fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.on_select and self.on_select())
        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="＋ Add files", style="Accent.TButton", command=self.add_dialog).pack(side="left")
        ttk.Button(bar, text="Remove", command=self.remove).pack(side="left", padx=6)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left")
        if ordered:
            ttk.Button(bar, text="▼", width=3, command=lambda: self.move(1)).pack(side="right")
            ttk.Button(bar, text="▲", width=3, command=lambda: self.move(-1)).pack(side="right", padx=4)
        self.count = ttk.Label(bar, text="", style="CardSub.TLabel")
        self.count.pack(side="right", padx=10)
        if HAS_DND:
            self.lb.drop_target_register(DND_FILES)
            self.lb.dnd_bind("<<Drop>>", lambda e: self.add(self.tk.splitlist(e.data)))
            ttk.Label(self, text="Tip: you can drag & drop files onto the list", style="CardSub.TLabel").pack(anchor="w", pady=(4, 0))
        self._refresh_count()

    def _refresh_count(self):
        self.count.config(text=f"{len(self.paths)} file(s)")

    def add_dialog(self):
        self.add(filedialog.askopenfilenames(filetypes=self.types))

    def add(self, paths):
        for p in paths:
            if os.path.isfile(p) and p not in self.paths:
                self.paths.append(p)
                self.lb.insert("end", os.path.basename(p) + "    —    " + os.path.dirname(p))
        self._refresh_count()
        if self.paths and not self.lb.curselection():
            self.lb.selection_set(0)
            if self.on_select:
                self.on_select()

    def remove(self):
        for i in reversed(self.lb.curselection()):
            self.lb.delete(i)
            del self.paths[i]
        self._refresh_count()

    def clear(self):
        self.lb.delete(0, "end")
        self.paths.clear()
        self._refresh_count()

    def move(self, d):
        sel = self.lb.curselection()
        if len(sel) != 1:
            return
        i, j = sel[0], sel[0] + d
        if not 0 <= j < len(self.paths):
            return
        self.paths[i], self.paths[j] = self.paths[j], self.paths[i]
        text = self.lb.get(i)
        self.lb.delete(i)
        self.lb.insert(j, text)
        self.lb.selection_set(j)

    def first_selected(self):
        sel = self.lb.curselection()
        if sel:
            return self.paths[sel[0]]
        return self.paths[0] if self.paths else None


# ======================================================================
#  Main application
# ======================================================================
BaseTk = TkinterDnD.Tk if HAS_DND else tk.Tk


class App(BaseTk):
    def __init__(self):
        super().__init__()
        self._dpi_awareness()
        self.title(f"{APP_NAME}")
        self.geometry("1180x780")
        self.minsize(980, 640)
        try:
            self.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.cfg = core.load_config()
        self.busy = False
        self.last_out = None
        fams = set(tkfont.families())
        self.family = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "DejaVu Sans", "Arial") if f in fams), "TkDefaultFont")
        self.font = (self.family, 10)
        self.style = ttk.Style(self)
        self.apply_theme()
        self._build_shell()
        self.bind_all("<Control-d>", lambda e: self.toggle_theme())
        for i, (name, _, _) in enumerate(PAGES[:6], 1):
            self.bind_all(f"<Control-Key-{i}>", lambda e, n=name: self.show_page(n))
        self.show_page("Home")

    # ------------------------------------------------------------ theme
    @staticmethod
    def _dpi_awareness():
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    def apply_theme(self):
        t = self.t = THEMES[self.cfg.get("theme", "light")]
        s, F = self.style, self.family
        s.theme_use("clam")
        self.configure(bg=t["bg"])
        s.configure(".", background=t["bg"], foreground=t["fg"], font=(F, 10), bordercolor=t["border"],
                    lightcolor=t["bg"], darkcolor=t["bg"], troughcolor=t["border"], fieldbackground=t["field"],
                    focuscolor=t["accent"])
        s.configure("TFrame", background=t["bg"])
        s.configure("Card.TFrame", background=t["panel"], bordercolor=t["border"], borderwidth=1, relief="solid")
        s.configure("Flat.TFrame", background=t["panel"])
        s.configure("Side.TFrame", background=t["side"])
        s.configure("TLabel", background=t["bg"], foreground=t["fg"])
        s.configure("Card.TLabel", background=t["panel"], foreground=t["fg"])
        s.configure("CardTitle.TLabel", background=t["panel"], foreground=t["fg"], font=(F, 12, "bold"))
        s.configure("Sub.TLabel", foreground=t["sub"])
        s.configure("CardSub.TLabel", background=t["panel"], foreground=t["sub"])
        s.configure("Side.TLabel", background=t["side"], foreground=t["sub"], font=(F, 9, "bold"))
        s.configure("Brand.TLabel", background=t["side"], foreground=t["accent"], font=(F, 15, "bold"))
        s.configure("H1.TLabel", font=(F, 22, "bold"))
        s.configure("Status.TLabel", background=t["side"], foreground=t["sub"], padding=(14, 6))
        s.configure("TButton", background=t["panel"], foreground=t["fg"], padding=(12, 7), borderwidth=1,
                    bordercolor=t["border"], focusthickness=0)
        s.map("TButton", background=[("active", t["sel"])], bordercolor=[("active", t["accent"])])
        s.configure("Accent.TButton", background=t["accent"], foreground="white", bordercolor=t["accent"],
                    font=(F, 10, "bold"))
        s.map("Accent.TButton", background=[("active", t["accent_h"]), ("disabled", t["border"])])
        s.configure("Nav.TButton", background=t["side"], foreground=t["fg"], anchor="w", padding=(14, 10),
                    borderwidth=0, font=(F, 10))
        s.map("Nav.TButton", background=[("active", t["sel"])])
        s.configure("NavActive.TButton", background=t["sel"], foreground=t["accent"], anchor="w", padding=(14, 10),
                    borderwidth=0, font=(F, 10, "bold"))
        s.map("NavActive.TButton", background=[("active", t["sel"])])
        s.configure("Tile.TButton", background=t["panel"], foreground=t["accent"], anchor="w", padding=(10, 8),
                    font=(F, 10, "bold"))
        s.configure("TEntry", fieldbackground=t["field"], foreground=t["fg"], bordercolor=t["border"], padding=6)
        s.configure("TCombobox", fieldbackground=t["field"], background=t["field"], foreground=t["fg"],
                    arrowcolor=t["fg"], padding=5)
        s.map("TCombobox", fieldbackground=[("readonly", t["field"])], foreground=[("readonly", t["fg"])])
        self.option_add("*TCombobox*Listbox.background", t["field"])
        self.option_add("*TCombobox*Listbox.foreground", t["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
        s.configure("TSpinbox", fieldbackground=t["field"], foreground=t["fg"], arrowcolor=t["fg"], padding=5)
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(w, background=t["bg"], foreground=t["fg"])
            s.configure("Card." + w, background=t["panel"], foreground=t["fg"])
            s.map("Card." + w, background=[("active", t["panel"])])
            s.map(w, background=[("active", t["bg"])])
        s.configure("TSeparator", background=t["border"])
        s.configure("Horizontal.TProgressbar", background=t["accent"], troughcolor=t["border"], borderwidth=0)

    def toggle_theme(self):
        self.cfg["theme"] = "dark" if self.cfg.get("theme") == "light" else "light"
        core.save_config(self.cfg)
        self.apply_theme()
        for w in self.winfo_children():
            w.destroy()
        self._build_shell()
        self.show_page(self.current)

    def set_theme(self, name):
        if self.cfg.get("theme") == name:
            return
        self.cfg["theme"] = name
        core.save_config(self.cfg)
        self.apply_theme()
        for w in self.winfo_children():
            w.destroy()
        self._build_shell()
        self.show_page(self.current)

    # ------------------------------------------------------------ shell
    def _build_shell(self):
        side = ttk.Frame(self, style="Side.TFrame", width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ttk.Label(side, text="◆  Syntax Convert", style="Brand.TLabel").pack(anchor="w", padx=16, pady=(20, 18))
        ttk.Label(side, text="WORKSPACE", style="Side.TLabel").pack(anchor="w", padx=16, pady=(0, 6))
        self.nav = {}
        for i, (name, icon, _) in enumerate(PAGES, 1):
            b = ttk.Button(side, text=f"  {icon}   {name}", style="Nav.TButton", command=lambda n=name: self.show_page(n))
            b.pack(fill="x", padx=8, pady=1)
            self.nav[name] = b
        ttk.Label(side, text="🔒 Everything runs locally.\nYour files never leave\nthis computer.", style="Side.TLabel",
                  justify="left").pack(side="bottom", anchor="w", padx=16, pady=16)

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        # status bar
        bar = ttk.Frame(right, style="Side.TFrame")
        bar.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="Ready")
        self.status_lbl = ttk.Label(bar, textvariable=self.status, style="Status.TLabel")
        self.status_lbl.pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.progress.pack(side="right", padx=14)
        self.open_btn = ttk.Button(bar, text="Open folder", command=self.open_last)
        self.content = ttk.Frame(right, padding=(28, 22, 28, 12))
        self.content.pack(side="top", fill="both", expand=True)
        self.current = getattr(self, "current", "Home")

    def show_page(self, name):
        if self.busy:
            return
        self.current = name
        for w in self.content.winfo_children():
            w.destroy()
        for n, b in self.nav.items():
            b.configure(style="NavActive.TButton" if n == name else "Nav.TButton")
        method = next(m for n, _, m in PAGES if n == name)
        getattr(self, method)()

    # ------------------------------------------------------------ small UI helpers
    def heading(self, title, desc=""):
        ttk.Label(self.content, text=title, style="H1.TLabel").pack(anchor="w")
        if desc:
            ttk.Label(self.content, text=desc, style="Sub.TLabel", wraplength=800, justify="left").pack(anchor="w", pady=(4, 14))

    def card(self, title=None, pad=16, fill="x", expand=False, pady=(0, 12)):
        f = ttk.Frame(self.content, style="Card.TFrame", padding=pad)
        f.pack(fill=fill, expand=expand, pady=pady)
        if title:
            ttk.Label(f, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        return f

    def row(self, parent, pady=4):
        r = ttk.Frame(parent, style="Flat.TFrame")
        r.pack(fill="x", pady=pady)
        return r

    def labeled(self, parent, text, widget_factory, **pack):
        ttk.Label(parent, text=text, style="Card.TLabel").pack(side="left", padx=(0, 6))
        w = widget_factory(parent)
        w.pack(side="left", padx=(0, 16), **pack)
        return w

    def set_status(self, msg, kind=None):
        self.status.set(msg)
        self.status_lbl.configure(foreground=self.t.get(kind, self.t["sub"]) if kind else self.t["sub"])

    def ask_open(self, multiple, types):
        r = filedialog.askopenfilenames(filetypes=types) if multiple else filedialog.askopenfilename(filetypes=types)
        return list(r) if multiple else (r or "")

    def ask_save(self, title, ext, types, initial=None):
        return filedialog.asksaveasfilename(title=title, defaultextension=ext, filetypes=types,
                                            initialfile=initial or "", initialdir=self.cfg.get("output_dir") or None)

    def ask_dir(self, title="Choose output folder"):
        return filedialog.askdirectory(title=title, initialdir=self.cfg.get("output_dir") or None)

    def guard(self, fn):
        """Wrap a click handler so errors become a dialog instead of a traceback."""
        def run():
            try:
                fn()
            except Exception as e:
                self.set_status("Something went wrong", "err")
                messagebox.showerror(APP_NAME, str(e))
        return run

    # ------------------------------------------------------------ background tasks
    def run_bg(self, work, label="Working…"):
        """work() runs in a thread and returns (message, output_path|None[, details])."""
        if self.busy:
            messagebox.showinfo(APP_NAME, "Please wait for the current task to finish.")
            return
        self.busy = True
        self.open_btn.pack_forget()
        self.progress.start(12)
        self.set_status(label)

        def target():
            try:
                res = work()
            except Exception as e:  # noqa
                res = e
            self.after(0, self._bg_done, res)
        threading.Thread(target=target, daemon=True).start()

    def _bg_done(self, res):
        self.busy = False
        self.progress.stop()
        if isinstance(res, Exception):
            self.set_status("Failed", "err")
            messagebox.showerror(APP_NAME, str(res))
            return
        msg, out, *rest = res if isinstance(res, tuple) else (res, None)
        self.set_status("✓ " + msg, "ok")
        if out:
            self.last_out = out
            rec = [r for r in self.cfg.get("recent", []) if r != out][:9]
            self.cfg["recent"] = [out] + rec
            core.save_config(self.cfg)
            self.open_btn.pack(side="right", padx=4, pady=3)
            if self.cfg.get("open_after"):
                self.open_last()
        if rest and rest[0]:
            messagebox.showinfo(APP_NAME, msg + "\n\n" + rest[0])

    def open_last(self):
        if self.last_out:
            p = Path(self.last_out)
            try:
                core.open_path(p if p.is_dir() else p.parent)
            except Exception as e:
                messagebox.showerror(APP_NAME, str(e))

    # ============================================================ HOME
    def page_home(self):
        self.heading("Welcome back 👋", "Pick a tool to get started. Tip: Ctrl+1…6 switches pages, Ctrl+D toggles dark mode.")
        tiles = [
            ("🖼  Resize images", "Exact pixels or percent, DPI, batch mode, strip metadata.", "Image Resize"),
            ("🔁  Convert images", "Batch convert between 30+ formats, quality control.", "Image Convert"),
            ("📄  PDF toolkit", "Merge, split, rotate, watermark, compress, protect and more.", "PDF Tools"),
            ("📑  Office converter", "Word / Excel / PowerPoint ⇄ PDF and more.", "Office Convert"),
            ("🧰  Utilities", "OCR, summarize, QR codes, file hashes, batch rename.", "Utilities"),
        ]
        grid = ttk.Frame(self.content)
        grid.pack(fill="x")
        for i, (title, desc, target) in enumerate(tiles):
            c = ttk.Frame(grid, style="Card.TFrame", padding=16)
            c.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0, 12), pady=(0, 12))
            grid.columnconfigure(i % 3, weight=1, uniform="t")
            ttk.Label(c, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(c, text=desc, style="CardSub.TLabel", wraplength=230, justify="left").pack(anchor="w", pady=(6, 10))
            ttk.Button(c, text="Open →", style="Accent.TButton", command=lambda t=target: self.show_page(t)).pack(anchor="w")

        rec = self.card("Recent output (double-click to open folder)", fill="both", expand=True)
        lb = tk.Listbox(rec, height=6, bg=self.t["field"], fg=self.t["fg"], relief="flat", activestyle="none",
                        selectbackground=self.t["accent"], highlightthickness=1, highlightbackground=self.t["border"],
                        font=self.font)
        lb.pack(fill="both", expand=True)
        recent = [r for r in self.cfg.get("recent", []) if os.path.exists(r)]
        for r in recent:
            lb.insert("end", r)
        if not recent:
            lb.insert("end", "Nothing yet — files you create will show up here.")

        def open_sel(_):
            if lb.curselection() and recent:
                core.open_path(Path(recent[lb.curselection()[0]]).parent)
        lb.bind("<Double-Button-1>", open_sel)

    # ============================================================ IMAGE RESIZE
    def page_resize(self):
        self.heading("Resize images", "One image or a whole batch. Set exact pixels or a percentage, DPI and output format.")
        if Image is None:
            ttk.Label(self.content, text="Pillow is not installed.  pip install Pillow").pack(anchor="w")
            return
        top = ttk.Frame(self.content)
        top.pack(fill="x")
        left = ttk.Frame(top, style="Card.TFrame", padding=16)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.rs_files = FileList(self, left, IMG_T, height=5, on_select=self._rs_preview)
        self.rs_files.pack(fill="both", expand=True)
        prev = ttk.Frame(top, style="Card.TFrame", padding=12, width=240)
        prev.pack(side="left", fill="y")
        prev.pack_propagate(False)
        ttk.Label(prev, text="Preview", style="CardTitle.TLabel").pack(anchor="w")
        self.rs_prev = ttk.Label(prev, text="No image selected", style="CardSub.TLabel", anchor="center")
        self.rs_prev.pack(fill="both", expand=True)
        self.rs_info = ttk.Label(prev, text="", style="CardSub.TLabel", wraplength=210)
        self.rs_info.pack(anchor="w")

        opt = self.card("Options", pady=(12, 8))
        self.rs_mode = tk.StringVar(value="pixels")
        self.rs_w, self.rs_h = tk.StringVar(value="1200"), tk.StringVar(value="800")
        self.rs_pct, self.rs_dpi = tk.StringVar(value="50"), tk.StringVar(value="300")
        self.rs_fmt, self.rs_q = tk.StringVar(value="PNG"), tk.StringVar(value="90")
        self.rs_keep, self.rs_strip = tk.BooleanVar(value=True), tk.BooleanVar(value=True)

        r = self.row(opt)
        ttk.Radiobutton(r, text="By pixels", value="pixels", variable=self.rs_mode, style="Card.TRadiobutton").pack(side="left", padx=(0, 10))
        self.labeled(r, "Width", lambda p: ttk.Entry(p, textvariable=self.rs_w, width=8))
        self.labeled(r, "Height", lambda p: ttk.Entry(p, textvariable=self.rs_h, width=8))
        ttk.Checkbutton(r, text="Keep aspect ratio", variable=self.rs_keep, style="Card.TCheckbutton").pack(side="left")
        r = self.row(opt)
        ttk.Radiobutton(r, text="By percent", value="percent", variable=self.rs_mode, style="Card.TRadiobutton").pack(side="left", padx=(0, 10))
        self.labeled(r, "Scale %", lambda p: ttk.Entry(p, textvariable=self.rs_pct, width=8))
        r = self.row(opt, pady=(10, 4))
        self.labeled(r, "Format", lambda p: ttk.Combobox(p, textvariable=self.rs_fmt, values=list(core.PIL_SAVE), state="readonly", width=8))
        self.labeled(r, "DPI", lambda p: ttk.Entry(p, textvariable=self.rs_dpi, width=6))
        self.labeled(r, "Quality (JPEG/WEBP)", lambda p: ttk.Spinbox(p, from_=1, to=100, textvariable=self.rs_q, width=5))
        ttk.Checkbutton(r, text="Strip metadata (EXIF / GPS)", variable=self.rs_strip, style="Card.TCheckbutton").pack(side="left")

        act = self.row(self.content, pady=6)
        ttk.Button(act, text="Resize & export", style="Accent.TButton", command=self.guard(self.do_resize)).pack(side="left")
        ttk.Button(act, text="Rotate 90°", command=self.guard(lambda: self.simple_image("rotate"))).pack(side="left", padx=(16, 6))
        ttk.Button(act, text="Flip", command=self.guard(lambda: self.simple_image("flip"))).pack(side="left", padx=6)
        ttk.Button(act, text="Add text watermark", command=self.guard(self.do_watermark)).pack(side="left", padx=6)
        ttk.Button(act, text="Remove metadata only", command=self.guard(lambda: self.simple_image("strip"))).pack(side="left", padx=6)

    def _rs_preview(self):
        p = self.rs_files.first_selected()
        if not p:
            return
        try:
            with Image.open(p) as im:
                w, h = im.size
                im.thumbnail((210, 180))
                self._prev_img = ImageTk.PhotoImage(im.convert("RGBA"))
            self.rs_prev.configure(image=self._prev_img, text="")
            self.rs_info.configure(text=f"{Path(p).name}\n{w} × {h} px  •  {os.path.getsize(p) / 1024:,.0f} KB")
        except Exception:
            self.rs_prev.configure(image="", text="Can't preview this file")

    def _need_files(self, fl):
        if not fl.paths:
            raise ValueError("Add at least one file first.")
        return list(fl.paths)

    def do_resize(self):
        files = self._need_files(self.rs_files)
        fmt = self.rs_fmt.get()
        ext = core.PIL_SAVE[fmt]
        try:
            kw = dict(mode=self.rs_mode.get(), keep_ratio=self.rs_keep.get(), dpi=int(self.rs_dpi.get() or 300),
                      quality=int(self.rs_q.get() or 90), keep_exif=not self.rs_strip.get())
            if kw["mode"] == "percent":
                kw["percent"] = float(self.rs_pct.get())
            else:
                kw["width"], kw["height"] = int(self.rs_w.get()), int(self.rs_h.get())
        except ValueError:
            raise ValueError("Width, height, DPI, quality and percent must be numbers.")
        if len(files) == 1:
            out = self.ask_save("Save resized image", ext, [(fmt, f"*{ext}")], Path(files[0]).stem + "_resized" + ext)
            if not out:
                return
            jobs = [(files[0], out)]
            dest = out
        else:
            folder = self.ask_dir()
            if not folder:
                return
            jobs = [(f, core.unique_path(os.path.join(folder, Path(f).stem + "_resized" + ext))) for f in files]
            dest = folder

        def work():
            errs, size = [], None
            for src, out in jobs:
                try:
                    size = core.resize_image_file(src, out, fmt, **kw)
                except Exception as e:  # noqa
                    errs.append(f"{Path(src).name}: {e}")
            ok = len(jobs) - len(errs)
            msg = f"Resized {ok} of {len(jobs)} image(s)" + (f" → {size[0]}×{size[1]} px" if size and len(jobs) == 1 else "")
            return msg, dest, "\n".join(errs[:8])
        self.run_bg(work, "Resizing…")

    def simple_image(self, kind):
        p = self.rs_files.first_selected() or self.ask_open(False, IMG_T)
        if not p:
            return
        names = {"rotate": "_rotated", "flip": "_flipped", "strip": "_clean"}
        out = self.ask_save("Save image", Path(p).suffix, [("Image", core.IMAGE_EXT)], Path(p).stem + names[kind] + Path(p).suffix)
        if not out:
            return

        def work():
            if kind == "strip":
                core.strip_image_metadata(p, out)
            else:
                core.rotate_flip_image(p, out, kind)
            return "Image saved", out
        self.run_bg(work)

    def do_watermark(self):
        p = self.rs_files.first_selected() or self.ask_open(False, IMG_T)
        if not p:
            return
        text = simpledialog.askstring("Watermark", "Watermark text:")
        if not text:
            return
        out = self.ask_save("Save watermarked image", Path(p).suffix, [("Image", core.IMAGE_EXT)], Path(p).stem + "_wm" + Path(p).suffix)
        if not out:
            return
        self.run_bg(lambda: (core.watermark_image(p, out, text), ("Watermark added", out))[1])

    # ============================================================ IMAGE CONVERT
    def page_convert(self):
        self.heading("Convert images", "Batch-convert to JPG, PNG, WEBP, TIFF, PDF and more. Exotic formats use ImageMagick if installed.")
        if Image is None:
            ttk.Label(self.content, text="Pillow is not installed.  pip install Pillow").pack(anchor="w")
            return
        c = self.card("Images")
        self.cv_files = FileList(self, c, IMG_T, height=7)
        self.cv_files.pack(fill="x")
        o = self.card("Options")
        self.cv_fmt, self.cv_q, self.cv_dpi = tk.StringVar(value="WEBP"), tk.StringVar(value="90"), tk.BooleanVar(value=True)
        r = self.row(o)
        self.labeled(r, "Convert to", lambda p: ttk.Combobox(p, textvariable=self.cv_fmt, values=list(core.CONVERT_EXT), state="readonly", width=12))
        self.labeled(r, "Quality (JPG/WEBP)", lambda p: ttk.Spinbox(p, from_=1, to=100, textvariable=self.cv_q, width=5))
        ttk.Checkbutton(r, text="Keep DPI metadata", variable=self.cv_dpi, style="Card.TCheckbutton").pack(side="left")
        ttk.Label(o, text="JPG flattens transparency onto white. AVIF/HEIC/PSD/EXR/SVG need ImageMagick on your PATH.",
                  style="CardSub.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Button(self.content, text="Convert…", style="Accent.TButton", command=self.guard(self.do_convert)).pack(anchor="w")

    def do_convert(self):
        files = self._need_files(self.cv_files)
        folder = self.ask_dir()
        if not folder:
            return
        fmt, q, keep = self.cv_fmt.get(), max(1, min(100, int(self.cv_q.get() or 90))), self.cv_dpi.get()

        def work():
            saved, errs = 0, []
            for p in files:
                out = core.unique_path(os.path.join(folder, Path(p).stem + core.CONVERT_EXT[fmt]))
                try:
                    core.convert_image(p, out, fmt, q, keep)
                    saved += 1
                except Exception as e:  # noqa
                    errs.append(f"{Path(p).name}: {e}")
            return f"Converted {saved} of {len(files)} image(s) to {fmt}", folder, "\n".join(errs[:8])
        self.run_bg(work, "Converting…")

    # ============================================================ PDF
    def page_pdf(self):
        self.heading("PDF tools", "Merge with drag-to-reorder, or pick any one-click tool below.")
        c = self.card("Merge PDFs  (use ▲ ▼ to set the order)")
        self.pdf_files = FileList(self, c, PDF_T, height=4, ordered=True)
        self.pdf_files.pack(fill="x")
        ttk.Button(c, text="Merge into one PDF", style="Accent.TButton", command=self.guard(self.do_merge)).pack(anchor="w", pady=(10, 0))

        t = self.card("One-click tools")
        tools = [
            ("Split into pages", self.pdf_split), ("Rotate", self.pdf_rotate), ("Extract pages", self.pdf_extract),
            ("PDF → images", self.pdf_to_img), ("Images → PDF", self.pdf_from_imgs), ("Watermark", self.pdf_wm),
            ("Page numbers", self.pdf_nums), ("Protect (password)", self.pdf_prot), ("Unlock", self.pdf_unl),
            ("Compress", self.pdf_comp), ("Compare two PDFs", self.pdf_cmp), ("Repair", self.pdf_rep),
            ("Info / remove metadata", self.pdf_meta),
        ]
        g = ttk.Frame(t, style="Flat.TFrame")
        g.pack(fill="x")
        for i, (label, fn) in enumerate(tools):
            ttk.Button(g, text=label, command=self.guard(fn)).grid(row=i // 4, column=i % 4, sticky="ew", padx=4, pady=4)
            g.columnconfigure(i % 4, weight=1, uniform="b")

    def _pdf_in(self):
        return self.ask_open(False, PDF_T)

    def _simple_pdf(self, title, suffix, fn, label, needs_arg=None):
        p = self._pdf_in()
        if not p:
            return
        arg = None
        if needs_arg:
            arg = needs_arg()
            if arg is None:
                return
        out = self.ask_save(title, ".pdf", PDF_T, Path(p).stem + suffix + ".pdf")
        if not out:
            return
        self.run_bg(lambda: (fn(p, out, arg) if needs_arg else fn(p, out), (label, out))[1], label + "…")

    def do_merge(self):
        files = self._need_files(self.pdf_files)
        if len(files) < 2:
            raise ValueError("Add at least two PDFs to merge.")
        out = self.ask_save("Save merged PDF", ".pdf", PDF_T, "merged.pdf")
        if out:
            self.run_bg(lambda: (f"Merged {core.pdf_merge(files, out)} PDFs", out), "Merging…")

    def pdf_split(self):
        p = self._pdf_in()
        folder = p and self.ask_dir()
        if folder:
            self.run_bg(lambda: (f"Split into {core.pdf_split(p, folder)} pages", folder), "Splitting…")

    def pdf_rotate(self):
        def ask():
            a = simpledialog.askinteger("Rotate PDF", "Rotation angle (90, 180 or 270):", initialvalue=90)
            if a not in (90, 180, 270):
                return None
            return a
        self._simple_pdf("Save rotated PDF", "_rotated", core.pdf_rotate, "Rotated", ask)

    def pdf_extract(self):
        p = self._pdf_in()
        if not p:
            return
        R, _ = core.pypdf()
        total = len(R(p).pages)
        spec = simpledialog.askstring("Extract pages", f"Pages to keep (e.g. 1,3-5). This PDF has {total} pages:")
        if not spec:
            return
        core.parse_page_spec(spec, total)  # validate now, raises friendly error
        out = self.ask_save("Save extracted PDF", ".pdf", PDF_T, Path(p).stem + "_extract.pdf")
        if out:
            self.run_bg(lambda: (f"Extracted {core.pdf_extract(p, out, spec)} page(s)", out))

    def pdf_to_img(self):
        p = self._pdf_in()
        folder = p and self.ask_dir()
        if folder:
            self.run_bg(lambda: (f"Exported {core.pdf_to_images(p, folder)} page images", folder), "Rendering pages…")

    def pdf_from_imgs(self):
        files = self.ask_open(True, IMG_T)
        if not files:
            return
        out = self.ask_save("Save PDF", ".pdf", PDF_T, "images.pdf")
        if out:
            self.run_bg(lambda: (f"Created PDF from {core.images_to_pdf(files, out)} images", out))

    def pdf_wm(self):
        self._simple_pdf("Save watermarked PDF", "_watermarked", core.pdf_watermark, "Watermark added",
                         lambda: simpledialog.askstring("Watermark", "Watermark text:"))

    def pdf_nums(self):
        self._simple_pdf("Save numbered PDF", "_numbered", core.pdf_page_numbers, "Page numbers added")

    def pdf_prot(self):
        self._simple_pdf("Save protected PDF", "_protected", core.pdf_protect, "PDF protected",
                         lambda: simpledialog.askstring("Protect PDF", "Set a password:", show="*"))

    def pdf_unl(self):
        self._simple_pdf("Save unlocked PDF", "_unlocked", core.pdf_unlock, "PDF unlocked",
                         lambda: simpledialog.askstring("Unlock PDF", "Current password:", show="*") or "")

    def pdf_comp(self):
        p = self._pdf_in()
        if not p:
            return
        out = self.ask_save("Save compressed PDF", ".pdf", PDF_T, Path(p).stem + "_compressed.pdf")
        if out:
            def work():
                a, b = core.pdf_compress(p, out)
                note = "" if b < a else "  (no saving — this PDF is already optimized)"
                return f"{a / 1024:,.0f} KB → {b / 1024:,.0f} KB{note}", out
            self.run_bg(work, "Compressing…")

    def pdf_cmp(self):
        files = self.ask_open(True, PDF_T)
        if len(files) != 2:
            if files:
                raise ValueError("Select exactly two PDFs.")
            return
        out = self.ask_save("Save comparison report", ".txt", [("Text", "*.txt")], "comparison.txt")
        if out:
            self.run_bg(lambda: (f"Report saved ({core.pdf_compare(files[0], files[1], out)} diff lines)", out), "Comparing…")

    def pdf_rep(self):
        self._simple_pdf("Save rewritten PDF", "_repaired", core.pdf_repair, "PDF rewritten")

    def pdf_meta(self):
        p = self._pdf_in()
        if not p:
            return
        info = core.pdf_info(p)
        if messagebox.askyesno("PDF info", info + "\n\nSave a copy with metadata removed?"):
            out = self.ask_save("Save clean PDF", ".pdf", PDF_T, Path(p).stem + "_clean.pdf")
            if out:
                self.run_bg(lambda: (core.pdf_strip_metadata(p, out), ("Metadata removed", out))[1])

    # ============================================================ OFFICE
    def page_office(self):
        self.heading("Office converter", "Word, Excel and PowerPoint conversions use LibreOffice (auto-detected). PDF → Word uses pdf2docx.")
        lo = core.find_libreoffice()
        ttk.Label(self.content, text=("✓ LibreOffice found" if lo else "✗ LibreOffice not found — install it from libreoffice.org for Office ⇄ PDF"),
                  foreground=self.t["ok"] if lo else self.t["err"]).pack(anchor="w", pady=(0, 10))
        opts = [
            ("Word → PDF", ("docx", "doc", "odt", "rtf", "txt"), "pdf"), ("PowerPoint → PDF", ("pptx", "ppt", "odp"), "pdf"),
            ("Excel / CSV → PDF", ("xlsx", "xls", "ods", "csv", "tsv"), "pdf"), ("PDF → Word (DOCX)", ("pdf",), "docx"),
            ("Word → HTML", ("docx", "odt"), "html"), ("Word → EPUB", ("docx", "odt"), "epub"),
            ("Excel → CSV", ("xlsx", "xls", "ods"), "csv"), ("CSV → Excel", ("csv", "tsv"), "xlsx"),
            ("HTML → PDF", ("html", "htm"), "pdf"), ("Office → ODT", ("docx", "doc", "rtf"), "odt"),
            ("Office → TXT", ("docx", "odt", "rtf"), "txt"), ("PDF → Markdown", ("pdf",), "md"),
            ("Word → Markdown", ("docx",), "md"),
        ]
        c = self.card()
        for i, (label, exts, oe) in enumerate(opts):
            ttk.Button(c, text=label, command=self.guard(lambda l=label, e=exts, o=oe: self.do_office(l, e, o))).grid(
                row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
            c.columnconfigure(i % 3, weight=1, uniform="o")
        ttk.Label(self.content, text="PDF → Word is best-effort and layout dependent; scanned PDFs need OCR first.",
                  style="Sub.TLabel").pack(anchor="w", pady=6)

    def do_office(self, label, exts, out_ext):
        p = self.ask_open(False, [("Supported files", " ".join("*." + e for e in exts)), ("All files", "*.*")])
        if not p:
            return
        out = self.ask_save("Save converted file", "." + out_ext, [(out_ext.upper(), "*." + out_ext)], Path(p).stem + "." + out_ext)
        if out:
            self.run_bg(lambda: (core.office_convert(p, out, out_ext), (label + " finished", out))[1], label + "…")

    # ============================================================ UTILITIES
    def page_utils(self):
        self.heading("Utilities", "Small helpers that don't fit anywhere else.")
        c = self.card()
        tools = [
            ("OCR a PDF → text", self.u_ocr), ("Summarize PDF / text", self.u_sum), ("Translate text file", self.u_tr),
            ("QR code generator", self.u_qr), ("File checksum (MD5 / SHA)", self.u_hash), ("Batch rename files", self.u_rename),
            ("Text file → PDF", self.u_txt2pdf), ("Scan / photos → PDF", self.pdf_from_imgs), ("What's not supported?", self.u_info),
        ]
        for i, (label, fn) in enumerate(tools):
            ttk.Button(c, text=label, command=self.guard(fn)).grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
            c.columnconfigure(i % 3, weight=1, uniform="u")

    def u_ocr(self):
        p = self._pdf_in()
        if not p:
            return
        lang = simpledialog.askstring("OCR language", "Tesseract language code (eng, hin, fra, deu, spa…):", initialvalue="eng")
        if not lang:
            return
        out = self.ask_save("Save OCR text", ".txt", [("Text", "*.txt")], Path(p).stem + "_ocr.txt")
        if out:
            self.run_bg(lambda: (Path(out).write_text(core.ocr_pdf(p, lang), encoding="utf-8"), ("OCR text saved", out))[1], "Running OCR…")

    def _read_text_source(self, p):
        return core.pdf_text(p) if p.lower().endswith(".pdf") else Path(p).read_text(encoding="utf-8", errors="ignore")

    def u_sum(self):
        p = self.ask_open(False, [("PDF or text", "*.pdf *.txt"), ("All files", "*.*")])
        if not p:
            return
        out = self.ask_save("Save summary", ".txt", [("Text", "*.txt")], Path(p).stem + "_summary.txt")
        if out:
            self.run_bg(lambda: (Path(out).write_text(core.summarize(self._read_text_source(p)), encoding="utf-8"), ("Summary saved", out))[1], "Summarizing…")

    def u_tr(self):
        p = self.ask_open(False, [("Text files", "*.txt")])
        if not p:
            return
        if not messagebox.askyesno("Online service", "Translation sends your text to Google Translate over the internet.\nContinue?"):
            return
        lang = simpledialog.askstring("Translate", "Target language code (hi, fr, de, es, ja…):", initialvalue="hi")
        if not lang:
            return
        out = self.ask_save("Save translation", ".txt", [("Text", "*.txt")], Path(p).stem + f"_{lang}.txt")
        if out:
            self.run_bg(lambda: (Path(out).write_text(core.translate_text(Path(p).read_text(encoding="utf-8", errors="ignore"), lang), encoding="utf-8"), ("Translation saved", out))[1], "Translating…")

    def u_qr(self):
        text = simpledialog.askstring("QR code", "Text or URL to encode:")
        if not text:
            return
        out = self.ask_save("Save QR code", ".png", [("PNG", "*.png")], "qrcode.png")
        if out:
            self.run_bg(lambda: (core.make_qr(text, out), ("QR code saved", out))[1])

    def u_hash(self):
        p = self.ask_open(False, [("All files", "*.*")])
        if not p:
            return
        h = core.file_hashes(p)
        txt = f"{Path(p).name}\n\n" + "\n".join(f"{k.upper():7}{v}" for k, v in h.items())
        self.clipboard_clear()
        self.clipboard_append(h["sha256"])
        messagebox.showinfo("Checksums", txt + "\n\n(SHA-256 copied to clipboard)")

    def u_rename(self):
        files = self.ask_open(True, [("All files", "*.*")])
        if not files:
            return
        pat = simpledialog.askstring("Batch rename", "New name pattern ({n} = counter, {name} = old name).\nExample: holiday_{n:03d}", initialvalue="file_{n:03d}")
        if not pat:
            return
        if messagebox.askyesno("Confirm", f"Rename {len(files)} file(s) using '{pat}'?\nThis can't be undone."):
            done = core.batch_rename(sorted(files), pat)
            self.set_status(f"✓ Renamed {len(done)} file(s)", "ok")
            self.last_out = done[0][1] if done else None
            if self.last_out:
                self.open_btn.pack(side="right", padx=4, pady=3)

    def u_txt2pdf(self):
        p = self.ask_open(False, [("Text files", "*.txt")])
        if not p:
            return
        out = self.ask_save("Save PDF", ".pdf", PDF_T, Path(p).stem + ".pdf")
        if out:
            self.run_bg(lambda: (core.text_to_pdf(p, out), ("PDF created", out))[1])

    def u_info(self):
        messagebox.showinfo("Not included (yet)",
                            "• Digital signatures — use a certificate-based signing tool\n"
                            "• Permanent redaction — use a redaction-aware library and verify\n"
                            "• Interactive form filling\n"
                            "• PDF → PowerPoint / Excel\n\nThe app says so instead of faking these.")

    # ============================================================ SETTINGS
    def page_settings(self):
        self.heading("Settings")
        c = self.card("Appearance")
        r = self.row(c)
        current = self.cfg.get("theme", "light")
        ttk.Button(r, text="☀  Light", width=12,
                   style="Accent.TButton" if current == "light" else "TButton",
                   command=lambda: self.set_theme("light")).pack(side="left", padx=(0, 8))
        ttk.Button(r, text="☾  Dark", width=12,
                   style="Accent.TButton" if current == "dark" else "TButton",
                   command=lambda: self.set_theme("dark")).pack(side="left")
        ttk.Label(c, text="Shortcut: Ctrl+D", style="CardSub.TLabel").pack(anchor="w", pady=(6, 0))
        c = self.card("Output")
        r = self.row(c)
        self.set_dir = tk.StringVar(value=self.cfg.get("output_dir", ""))
        ttk.Entry(r, textvariable=self.set_dir).pack(side="left", fill="x", expand=True, padx=(0, 8))

        def pick():
            d = filedialog.askdirectory()
            if d:
                self.set_dir.set(d)
                self.cfg["output_dir"] = d
                core.save_config(self.cfg)
        ttk.Button(r, text="Default save folder…", command=pick).pack(side="left")
        self.set_open = tk.BooleanVar(value=self.cfg.get("open_after", False))

        def toggle():
            self.cfg["open_after"] = self.set_open.get()
            core.save_config(self.cfg)
        ttk.Checkbutton(c, text="Open the output folder when a task finishes", variable=self.set_open,
                        command=toggle, style="Card.TCheckbutton").pack(anchor="w", pady=(8, 0))


if __name__ == "__main__":
    App().mainloop()
