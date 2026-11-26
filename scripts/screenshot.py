"""Capture le tableau de bord Grafana sur la fenetre de chaque tir (Edge headless).
Usage : python scripts/screenshot.py <nom> [<nom> ...]   (Grafana sur localhost:13000)
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
RES = Path(__file__).resolve().parent.parent / "results"


def ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


for name in sys.argv[1:]:
    w = json.loads((RES / f"{name}-window.json").read_text())
    frm, to = ms(w["start"]) - 20_000, ms(w["end"]) + 10_000
    out = RES / f"grafana-{name}.png"
    url = f"http://localhost:13000/d/perf-lab-red/x?orgId=1&from={frm}&to={to}&kiosk"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={profile}", "--window-size=1600,1250",
                        "--virtual-time-budget=25000", f"--screenshot={out}", url],
                       capture_output=True, timeout=120)
    print(name, out, os.path.getsize(out) if out.exists() else "MISSING")
