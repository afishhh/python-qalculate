#!/usr/bin/env python3
import sys
from pathlib import Path
from hashlib import sha256
from base64 import urlsafe_b64encode

wheel_dir = Path(sys.argv[1])
record_path = next(wheel_dir.glob("*.dist-info")) / "RECORD"

record = record_path.open("w+")
for file in wheel_dir.glob("**/*"):
    if file.is_dir():
        continue

    path = str(file.relative_to(wheel_dir))
    if file == record_path:
        print(path, "", "", sep=",", file=record)
    else:
        data = file.read_bytes()
        hash = urlsafe_b64encode(sha256(data, usedforsecurity=False).digest()).decode().rstrip("=")
        print(path, f"sha256={hash}", len(data), sep=",", file=record)

record.close()
