"""Imprime report/rapport.html en PDF avec Edge headless, puis compte les pages."""
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "report" / "rapport.html"
out = ROOT / "Compte-rendu-TP-eBPF-Guerfali-Zaouali-Gharbi-Saidi.pdf"

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", src.as_uri()], capture_output=True, timeout=120)
print(out, "pages:", len(PdfReader(out).pages))
