#!/usr/local/bin/python
"""Test-only executable: real OCR plus a deliberately hanging descendant."""
import json
from pathlib import Path
import subprocess
import sys
import time

engine = subprocess.Popen(["/usr/bin/tesseract", *sys.argv[1:]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
descendant = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "ct-ocr-cleanup-probe"])
Path(sys.argv[1]).with_name("probe-pids.json").write_text(json.dumps([engine.pid, descendant.pid]))
time.sleep(60)
