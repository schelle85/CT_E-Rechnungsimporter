#!/usr/local/bin/python
"""Test-only executable exercising the actual OCR output file-size boundary."""
import os

while True:
    os.write(1, b"x" * 65536)
