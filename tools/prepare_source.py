from __future__ import annotations

import argparse
import gzip
import hashlib
import lzma
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unpack(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix == ".gz":
        opener = gzip.open
    elif suffix == ".xz":
        opener = lzma.open
    else:
        raise SystemExit("Supported archives: .gz and .xz")
    with opener(source, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore an archived source DXF into data/source/original.dxf")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--target", type=Path, default=Path("data/source/original.dxf"))
    parser.add_argument("--sha256", dest="expected_sha256")
    args = parser.parse_args()
    unpack(args.archive, args.target)
    digest = sha256(args.target)
    if args.expected_sha256 and digest.lower() != args.expected_sha256.lower():
        args.target.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 mismatch: {digest}")
    print(f"Restored: {args.target} ({args.target.stat().st_size:,} bytes)")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
