import os
import sys
import time
from pathlib import Path


def write_out(data: bytes):
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def write_err(data: bytes):
    sys.stderr.buffer.write(data)
    sys.stderr.buffer.flush()


mode = sys.argv[1] if len(sys.argv) > 1 else "streams"

if mode == "streams":
    write_out(b'{"event":"one"}\n')
    write_err(b"err-one\n")
    line = sys.stdin.buffer.readline()
    write_out(b"stdin:" + line)
    write_out(b"{malformed-json\n")
    write_err(b"err-two\n")
elif mode == "secret":
    secret = os.environ.get("SYNTH_SECRET", "").encode()
    split = max(1, len(secret) // 2)
    write_out(b"before:" + secret[:split])
    time.sleep(0.05)
    write_out(secret[split:] + b":after\n")
elif mode == "sleep":
    write_out(b"started\n")
    time.sleep(float(sys.argv[2]))
elif mode == "exit3":
    write_out(b"leaving\n")
    raise SystemExit(3)
elif mode == "partial":
    write_out(b"partial-without-newline")
elif mode == "artifact":
    planned = Path(sys.argv[2])
    surprise = Path(sys.argv[3])
    planned.parent.mkdir(parents=True, exist_ok=True)
    surprise.parent.mkdir(parents=True, exist_ok=True)
    planned.write_bytes(b'{"planned":true}\n')
    surprise.write_bytes(b"surprise-bytes\x00\xff")
    write_out(b'{"event":"artifact-written"}\n')
else:
    write_err(b"unknown mode\n")
    raise SystemExit(2)
