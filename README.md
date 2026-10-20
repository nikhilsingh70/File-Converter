# Syntax Converter

**Syntax Converter** is a desktop file-conversion and utility application built with Python and Tkinter. It provides image resizing and conversion, PDF tools, office-document conversion, and file utilities in one desktop interface.

> **Version:** 2.0  
> **Platform:** Windows-focused build script; the Python app may run on other platforms where its dependencies are supported.

## Features

### Image tools
- Resize images by exact width and height or by percentage
- Preserve aspect ratio when resizing
- Set output DPI and JPEG/WEBP quality
- Convert supported image formats in batches
- Rotate and flip images
- Add a text watermark
- Remove image metadata, including EXIF/GPS data

### PDF tools
- Merge, split, rotate, and extract PDF pages
- Add watermarks and page numbers
- Protect or unlock PDFs with a password
- Compress or repair PDFs
- View PDF metadata and extract text
- Convert PDF pages to images
- Convert images or text files to PDF
- Compare extracted text between PDFs
- Run OCR on scanned PDFs (requires Tesseract OCR)

### Office conversion
Office conversion uses LibreOffice for supported document conversions. PDF-to-DOCX uses `pdf2docx`.

### Utilities
The application also includes utilities such as text summarization, translation, QR-code generation, file hashes, and batch renaming. Some utilities require additional packages or external programs.

### Interface
- Light and dark themes
- Recent output list
- Optional drag-and-drop support
- Local file processing for the core conversion workflows

## Project structure

```text
Syntax-Converter/
├── main.py
├── core.py
├── requirements.txt
├── requirements-build.txt
├── build_exe.bat
├── installer.iss
├── README.md
├── .gitignore
└── app.ico                 # Optional application icon
```

## Requirements

- Python 3.10 or newer is recommended
- Windows for the supplied `build_exe.bat` workflow
- Packages listed in `requirements.txt`
- LibreOffice for office-document conversions
- ImageMagick for some less-common image formats
- Tesseract OCR for OCR features

Some features depend on optional external programs. The app displays an error message when a required dependency is missing.

## Run from source

Open a terminal in the project folder.

### Windows (PowerShell or Command Prompt)

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If the `py` launcher is unavailable, use `python` instead of `py -3` to create the virtual environment.

## Build the Windows executable

Run:

```bat
build_exe.bat
```

The script creates a virtual environment, installs `requirements-build.txt`, and uses PyInstaller to build the application.

Expected executable:

```text
dist/SyntaxConverter/SyntaxConverter.exe
```

The supplied build script uses PyInstaller's `--onedir` mode, so distribute the **entire** `dist/SyntaxConverter/` folder, not just the `.exe`.

## Build an installer (optional)

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php).
2. Build the application using `build_exe.bat`.
3. Open `installer.iss` in Inno Setup and compile it.

The installer output is configured as `SyntaxConverter-Setup.exe`.

## Image format notes

- Pillow handles the formats supported by the installed Pillow build.
- Some formats (for example, AVIF, HEIC/HEIF, PSD, EXR, or SVG) may require ImageMagick and may not work unless the required ImageMagick delegates/codecs are installed.
- Conversion support depends on the input format and the installed libraries.

## Privacy

The core conversion features process files locally on your computer. The translation feature uses an online translation service, so text submitted for translation may be sent to that service. External tools such as LibreOffice, ImageMagick, and Tesseract run on your computer.

## Troubleshooting

- **Missing Python package:** activate your virtual environment and run `pip install -r requirements.txt`.
- **Office conversion fails:** install LibreOffice and ensure the application can find it.
- **OCR fails:** install Tesseract OCR and ensure `tesseract` is on PATH, or install it in a location recognized by the app.
- **Some image formats fail:** install ImageMagick and ensure `magick` is on PATH.
- **Drag-and-drop is unavailable:** confirm `tkinterdnd2` installed correctly.

## Contributing

Contributions and bug reports are welcome. For code changes, please test the relevant tool before opening a pull request.

## License

No license has been selected for this repository yet. Add a `LICENSE` file before publishing if you want to define permissions for reuse and redistribution. Without a license, others generally do not receive explicit permission to reuse, modify, or distribute your code.

## Author

Add your name, contact details, and repository links here if you want them displayed publicly.
