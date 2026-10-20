"""Syntax Converter - core logic (no GUI imports, so it can be tested and reused)."""
import collections
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except Exception:  # Pillow missing
    Image = None

IS_WIN = sys.platform.startswith("win")
CONFIG_PATH = Path.home() / ".syntax_converter.json"
DEFAULT_CONFIG = {"theme": "light", "output_dir": "", "open_after": False, "recent": []}


# ----------------------------------------------------------------- config
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


# ----------------------------------------------------------------- helpers
def need(module, pip_name=None):
    """Import an optional module or raise a friendly error."""
    try:
        return __import__(module)
    except Exception:
        raise RuntimeError(f"This feature needs '{pip_name or module}'.\nInstall it with:  pip install {pip_name or module}")


def need_pillow():
    if Image is None:
        raise RuntimeError("This feature needs Pillow.\nInstall it with:  pip install Pillow")


def pypdf():
    try:
        from pypdf import PdfReader, PdfWriter
        return PdfReader, PdfWriter
    except Exception:
        raise RuntimeError("PDF features need 'pypdf'.\nInstall it with:  pip install pypdf")


def find_exe(names, windows_paths=()):
    """Find an external program on PATH or in common Windows install folders."""
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    if IS_WIN:
        for p in windows_paths:
            if os.path.exists(p):
                return p
    return None


def find_libreoffice():
    return find_exe(["soffice", "libreoffice"], [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"])


def find_magick():
    # NOTE: never use plain "convert" on Windows - that is a disk-format utility.
    names = ["magick"] if IS_WIN else ["magick", "convert"]
    return find_exe(names, [r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"])


def find_tesseract():
    return find_exe(["tesseract"], [r"C:\Program Files\Tesseract-OCR\tesseract.exe"])


def run_cmd(cmd, timeout=180):
    """subprocess.run without flashing a console window in a windowed .exe."""
    kw = {}
    if IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def open_path(path):
    path = str(path)
    if IS_WIN:
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def unique_path(path):
    """Return path, or 'name (2).ext' if it already exists - never overwrite silently."""
    p = Path(path)
    if not p.exists():
        return str(p)
    i = 2
    while True:
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return str(q)
        i += 1


def parse_page_spec(spec, total):
    """'1,3-5' -> [1,3,4,5]. Raises ValueError with a clear message."""
    ids = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = int(a), int(b)
                if a > b:
                    raise ValueError
                ids.extend(range(a, b + 1))
            else:
                ids.append(int(part))
        except ValueError:
            raise ValueError(f"Can't understand '{part}'. Use something like 1,3-5")
    ids = [n for n in ids if 1 <= n <= total]
    if not ids:
        raise ValueError(f"No valid pages. This PDF has {total} page(s).")
    return ids


# ----------------------------------------------------------------- images
IMAGE_EXT = "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif *.ico"
PIL_SAVE = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "TIFF": ".tiff", "BMP": ".bmp"}


def save_image(im, out, fmt, dpi=None, quality=90, keep_exif=False):
    need_pillow()
    fmt = fmt.upper()
    exif = None
    if keep_exif:
        try:
            exif = im.getexif().tobytes()
        except Exception:
            exif = None
    if fmt == "JPEG":
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            im = bg
        elif im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
    elif fmt == "BMP" and im.mode not in ("RGB", "L", "P"):
        im = im.convert("RGB")
    kw = {}
    if dpi:
        kw["dpi"] = (dpi, dpi)
    if fmt in ("JPEG", "WEBP"):
        kw["quality"] = int(quality)
    if exif and fmt in ("JPEG", "WEBP", "PNG", "TIFF"):
        kw["exif"] = exif
    im.save(out, format=fmt, **kw)


def resize_image_file(src, out, fmt, mode="pixels", width=None, height=None, percent=100,
                      keep_ratio=True, dpi=300, quality=90, keep_exif=False):
    need_pillow()
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if mode == "percent":
            if percent <= 0:
                raise ValueError("Percent must be positive.")
            w, h = max(1, round(im.width * percent / 100)), max(1, round(im.height * percent / 100))
            im = im.resize((w, h), Image.Resampling.LANCZOS)
        else:
            if not width or not height or width < 1 or height < 1:
                raise ValueError("Width and height must be positive numbers.")
            if keep_ratio:
                im = ImageOps.contain(im, (width, height), Image.Resampling.LANCZOS)
            else:
                im = im.resize((width, height), Image.Resampling.LANCZOS)
        save_image(im, out, fmt, dpi, quality, keep_exif)
        return im.size


CONVERT_EXT = {
    "JPG": ".jpg", "PNG": ".png", "WEBP": ".webp", "AVIF": ".avif", "HEIC": ".heic", "HEIF": ".heif",
    "TIFF": ".tiff", "BMP": ".bmp", "GIF": ".gif", "ICO": ".ico", "PSD": ".psd", "TGA": ".tga",
    "PPM": ".ppm", "PBM": ".pbm", "PGM": ".pgm", "JPEG2000": ".jp2", "ICNS": ".icns", "APNG": ".png",
    "DDS": ".dds", "PCX": ".pcx", "CUR": ".cur", "XPM": ".xpm", "XBM": ".xbm", "WBMP": ".wbmp",
    "PAM": ".pam", "PFM": ".pfm", "SGI": ".sgi", "HDR": ".hdr", "EXR": ".exr", "SVG": ".svg", "PDF": ".pdf",
}
PILLOW_FORMATS = {
    "JPG": "JPEG", "PNG": "PNG", "WEBP": "WEBP", "TIFF": "TIFF", "BMP": "BMP", "GIF": "GIF", "ICO": "ICO",
    "TGA": "TGA", "PPM": "PPM", "PBM": "PBM", "PGM": "PGM", "JPEG2000": "JPEG2000", "PCX": "PCX",
    "XPM": "XPM", "XBM": "XBM", "DDS": "DDS", "SGI": "SGI", "PFM": "PFM",
}


def convert_image(src, out, fmt, quality=90, keep_dpi=True):
    """Convert one image. Uses Pillow when it can, ImageMagick as a fallback."""
    fmt = fmt.upper()
    if fmt == "PDF":
        need_pillow()
        with Image.open(src) as im:
            im = im.convert("RGB") if im.mode not in ("RGB", "L") else im.copy()
            im.save(out, "PDF", resolution=300.0)
        return
    if Image is not None and fmt in PILLOW_FORMATS:
        try:
            with Image.open(src) as source:
                dpi = source.info.get("dpi") if keep_dpi else None
                im = source.copy()
            if fmt == "ICO":
                im = im.convert("RGBA")
                im.thumbnail((256, 256), Image.Resampling.LANCZOS)
                im.save(out, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            elif fmt == "GIF":
                if im.mode not in ("RGB", "L", "P"):
                    im = im.convert("P")
                im.save(out, format="GIF")
            elif fmt in ("JPG", "WEBP", "BMP"):
                if fmt == "WEBP" and im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if "transparency" in im.info else "RGB")
                d = dpi[0] if isinstance(dpi, tuple) else None
                save_image(im, out, PILLOW_FORMATS[fmt], d, quality)
            else:
                kw = {"dpi": dpi} if isinstance(dpi, tuple) else {}
                im.save(out, format=PILLOW_FORMATS[fmt], **kw)
            return
        except Exception:
            pass  # fall through to ImageMagick
    magick = find_magick()
    if not magick:
        raise RuntimeError(f"{fmt} isn't supported by the built-in image engine.\n"
                           "Install ImageMagick (and tick 'add to PATH') for extended formats.")
    r = run_cmd([magick, src, "-quality", str(quality), out])
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError((r.stderr or r.stdout or "ImageMagick conversion failed").strip())


def strip_image_metadata(src, out):
    """Re-save without EXIF/GPS/text metadata (orientation is baked into the pixels first)."""
    need_pillow()
    with Image.open(src) as im:
        fmt = im.format or "PNG"
        im = ImageOps.exif_transpose(im)
        if fmt == "JPEG" and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.save(out, format=fmt)


def rotate_flip_image(src, out, kind):
    need_pillow()
    with Image.open(src) as im:
        fmt = im.format or "PNG"
        im = im.rotate(-90, expand=True) if kind == "rotate" else ImageOps.mirror(im)
        if fmt == "JPEG" and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.save(out, format=fmt)


def watermark_image(src, out, text, opacity=190):
    need_pillow()
    with Image.open(src) as im:
        fmt = im.format or "PNG"
        base = im.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    size = max(16, base.width // 20)
    try:
        font = ImageFont.truetype("arial.ttf" if IS_WIN else "DejaVuSans.ttf", size)
    except Exception:
        try:
            font = ImageFont.load_default(size)
        except Exception:
            font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), text, font=font, stroke_width=2)
    x, y = base.width - (bbox[2] - bbox[0]) - 20, base.height - (bbox[3] - bbox[1]) - 20
    d.text((x, y), text, font=font, fill=(255, 255, 255, opacity), stroke_width=2, stroke_fill=(0, 0, 0, opacity))
    res = Image.alpha_composite(base, layer)
    if fmt == "JPEG":
        res = res.convert("RGB")
    res.save(out, format=fmt)


# ----------------------------------------------------------------- PDF
def write_pdf(writer, out):
    with open(out, "wb") as f:
        writer.write(f)


def pdf_merge(files, out):
    R, W = pypdf()
    w = W()
    for p in files:
        r = R(p)
        if r.is_encrypted:
            raise RuntimeError(f"'{Path(p).name}' is password-protected. Unlock it first.")
        for pg in r.pages:
            w.add_page(pg)
    write_pdf(w, out)
    return len(files)


def pdf_split(src, folder):
    R, W = pypdf()
    r = R(src)
    for i, page in enumerate(r.pages, 1):
        w = W()
        w.add_page(page)
        write_pdf(w, os.path.join(folder, f"{Path(src).stem}_page_{i}.pdf"))
    return len(r.pages)


def pdf_rotate(src, out, angle):
    R, W = pypdf()
    w = W()
    for page in R(src).pages:
        page.rotate(angle)
        w.add_page(page)
    write_pdf(w, out)


def pdf_extract(src, out, spec):
    R, W = pypdf()
    r = R(src)
    ids = parse_page_spec(spec, len(r.pages))
    w = W()
    for n in ids:
        w.add_page(r.pages[n - 1])
    write_pdf(w, out)
    return len(ids)


def _overlay_page(PdfReader, width, height, draw):
    canvas_mod = need("reportlab", "reportlab")
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    draw(c)
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def pdf_watermark(src, out, text):
    R, W = pypdf()
    r, w = R(src), W()
    cache = {}
    for pg in r.pages:
        pw, ph = float(pg.mediabox.width), float(pg.mediabox.height)
        key = (round(pw), round(ph))
        if key not in cache:
            def draw(c, pw=pw, ph=ph):
                c.saveState()
                c.setFillAlpha(0.2)
                c.setFont("Helvetica-Bold", max(24, min(pw, ph) / 8))
                c.translate(pw / 2, ph / 2)
                c.rotate(35)
                c.drawCentredString(0, 0, text)
                c.restoreState()
            cache[key] = _overlay_page(R, pw, ph, draw)
        pg.merge_page(cache[key])
        w.add_page(pg)
    write_pdf(w, out)


def pdf_page_numbers(src, out):
    R, W = pypdf()
    r, w = R(src), W()
    for i, pg in enumerate(r.pages, 1):
        pw, ph = float(pg.mediabox.width), float(pg.mediabox.height)

        def draw(c, pw=pw, i=i):
            c.setFont("Helvetica", 9)
            c.drawCentredString(pw / 2, 18, str(i))
        pg.merge_page(_overlay_page(R, pw, ph, draw))
        w.add_page(pg)
    write_pdf(w, out)


def pdf_protect(src, out, password):
    R, W = pypdf()
    w = W()
    for page in R(src).pages:
        w.add_page(page)
    w.encrypt(password)
    write_pdf(w, out)


def pdf_unlock(src, out, password):
    R, W = pypdf()
    r = R(src)
    if r.is_encrypted and not r.decrypt(password or ""):
        raise RuntimeError("Incorrect password or unsupported encryption.")
    w = W()
    for page in r.pages:
        w.add_page(page)
    write_pdf(w, out)


def pdf_compress(src, out):
    R, W = pypdf()
    w = W()
    for page in R(src).pages:
        try:
            page.compress_content_streams()
        except Exception:
            pass
        w.add_page(page)
    try:
        for pg in w.pages:
            for img in pg.images:
                try:
                    img.replace(img.image, quality=70)
                except Exception:
                    pass
    except Exception:
        pass
    write_pdf(w, out)
    return os.path.getsize(src), os.path.getsize(out)


def pdf_repair(src, out):
    R, W = pypdf()
    r = R(src, strict=False)
    w = W()
    for pg in r.pages:
        w.add_page(pg)
    write_pdf(w, out)


def pdf_info(src):
    R, _ = pypdf()
    r = R(src)
    meta = r.metadata or {}
    lines = [f"File: {Path(src).name}", f"Pages: {len(r.pages)}", f"Encrypted: {r.is_encrypted}"]
    for k, v in dict(meta).items():
        lines.append(f"{str(k).lstrip('/')}: {v}")
    return "\n".join(lines)


def pdf_strip_metadata(src, out):
    R, W = pypdf()
    w = W()
    for pg in R(src).pages:
        w.add_page(pg)
    w.add_metadata({})
    write_pdf(w, out)


def pdf_text(src):
    R, _ = pypdf()
    return "\n".join((pg.extract_text() or "") for pg in R(src).pages)


def pdf_compare(a, b, out):
    ta, tb = pdf_text(a).splitlines(), pdf_text(b).splitlines()
    diff = list(difflib.unified_diff(ta, tb, fromfile=Path(a).name, tofile=Path(b).name, lineterm=""))
    Path(out).write_text("\n".join(diff) if diff else "No text differences found.", encoding="utf-8")
    return len(diff)


def pdf_to_images(src, folder, zoom=2.0):
    fitz = need("fitz", "pymupdf")
    doc = fitz.open(src)
    for i, page in enumerate(doc, 1):
        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(
            os.path.join(folder, f"{Path(src).stem}_{i}.png"))
    n = len(doc)
    doc.close()
    return n


def images_to_pdf(files, out):
    need_pillow()
    imgs = []
    for p in files:
        with Image.open(p) as im:
            imgs.append(ImageOps.exif_transpose(im).convert("RGB"))
    imgs[0].save(out, save_all=True, append_images=imgs[1:])
    return len(imgs)


def text_to_pdf(src, out):
    need("reportlab", "reportlab")
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(out)
    pw, ph = c._pagesize
    margin, lead, y = 45, 14, ph - 50
    for line in Path(src).read_text(encoding="utf-8", errors="ignore").splitlines() or [""]:
        for chunk in simpleSplit(line, "Helvetica", 10, pw - 2 * margin) or [""]:
            if y < 45:
                c.showPage()
                y = ph - 50
            c.setFont("Helvetica", 10)
            c.drawString(margin, y, chunk)
            y -= lead
    c.save()


def ocr_pdf(src, lang="eng"):
    fitz = need("fitz", "pymupdf")
    pytesseract = need("pytesseract", "pytesseract")
    exe = find_tesseract()
    if not exe:
        raise RuntimeError("Tesseract OCR isn't installed (or not on PATH).\n"
                           "Windows: https://github.com/UB-Mannheim/tesseract/wiki")
    pytesseract.pytesseract.tesseract_cmd = exe
    need_pillow()
    doc = fitz.open(src)
    pages = []
    for pg in doc:
        pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pages.append(pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))), lang=lang))
    doc.close()
    return "\n\n".join(pages)


# ----------------------------------------------------------------- text tools
def summarize(text, n=8):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stop = set("the and for that with this from are was were have has had not but you your all can will its they their there which when what who how into than then them been being also more most other some such only over".split())
    freq = collections.Counter(w for w in words if w not in stop)
    scored = []
    for i, s in enumerate(sentences):
        ws = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", s.lower()) if w not in stop]
        if len(s.strip()) > 35 and ws:
            scored.append((sum(freq[w] for w in ws) / (len(ws) + 1), i, s.strip()))
    top = sorted(sorted(scored, reverse=True)[:n], key=lambda x: x[1])
    return "\n\n".join(x[2] for x in top) or "No extractable text found."


def translate_text(text, target):
    need("deep_translator", "deep-translator")
    from deep_translator import GoogleTranslator
    tr = GoogleTranslator(source="auto", target=target)
    chunks = [text[i:i + 4500] for i in range(0, len(text), 4500)]
    return "".join(tr.translate(c) or "" for c in chunks)


def file_hashes(path, algos=("md5", "sha1", "sha256")):
    hs = {a: hashlib.new(a) for a in algos}
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            for h in hs.values():
                h.update(block)
    return {a: h.hexdigest() for a, h in hs.items()}


def batch_rename(files, pattern, start=1):
    """pattern uses {n} for the counter and {name} for the original stem. Returns [(old,new)]."""
    if "{n" not in pattern and "{name}" not in pattern:
        raise ValueError("Pattern must contain {n} or {name}, e.g. holiday_{n:03d}")
    done = []
    for i, p in enumerate(files, start):
        src = Path(p)
        new = src.with_name(pattern.format(n=i, name=src.stem) + src.suffix)
        if new.exists() and new != src:
            new = Path(unique_path(new))
        src.rename(new)
        done.append((str(src), str(new)))
    return done


def make_qr(text, out, box=10):
    qrcode = need("qrcode", "qrcode[pil]")
    qrcode.make(text, box_size=box).save(out)


# ----------------------------------------------------------------- office
OFFICE_EXT = {".docx", ".doc", ".odt", ".rtf", ".txt", ".pptx", ".ppt", ".odp", ".xlsx", ".xls", ".ods",
              ".csv", ".tsv", ".html", ".htm", ".epub"}


def office_convert(src, out, out_ext):
    ext = Path(src).suffix.lower()
    out_ext = out_ext.lower()
    if ext in OFFICE_EXT and out_ext in ("pdf", "html", "epub", "csv", "xlsx", "odt", "txt"):
        lo = find_libreoffice()
        if not lo:
            raise RuntimeError("LibreOffice is required for this conversion.\nInstall it from libreoffice.org "
                               "(the app finds it automatically).")
        tmp = tempfile.mkdtemp(prefix="synconv_")
        try:
            r = run_cmd([lo, "--headless", "--convert-to", out_ext, "--outdir", tmp, src], timeout=300)
            gen = os.path.join(tmp, Path(src).stem + "." + out_ext)
            if r.returncode != 0 or not os.path.exists(gen):
                raise RuntimeError((r.stderr or r.stdout or f"LibreOffice could not convert to {out_ext.upper()}").strip())
            if os.path.exists(out):
                os.remove(out)
            shutil.move(gen, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    elif ext == ".pdf" and out_ext == "docx":
        need("pdf2docx", "pdf2docx")
        from pdf2docx import Converter
        cv = Converter(src)
        try:
            cv.convert(out)
        finally:
            cv.close()
    elif ext == ".pdf" and out_ext == "md":
        Path(out).write_text(pdf_text(src), encoding="utf-8")
    elif ext == ".docx" and out_ext == "md":
        need("docx", "python-docx")
        from docx import Document
        Path(out).write_text("\n\n".join(p.text for p in Document(src).paragraphs), encoding="utf-8")
    else:
        raise RuntimeError(f"Converting {ext or 'this file'} to .{out_ext} isn't supported yet.")
