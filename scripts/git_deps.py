#!/usr/bin/env python3
"""Stage checksum-pinned AROS local-repository libgit2 independently."""
import hashlib, shutil, subprocess, tarfile, tempfile, urllib.request
from pathlib import Path
NAME = "libgit2-sys-0.18.5+1.9.4"
CHECKSUM = "005d6ae6eac1912906073e069f7db60b1fa98e052a68227824afe3e3a1c59ca2"
ROOT = Path(__file__).resolve().parents[1]

def stage(build_root, deps, snapshot):
    cache = build_root / "dependency-archives"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (NAME + ".crate")
    if not archive.exists():
        data = urllib.request.urlopen("https://static.crates.io/crates/libgit2-sys/" + NAME + ".crate", timeout=60).read()
        if hashlib.sha256(data).hexdigest() != CHECKSUM:
            raise RuntimeError("libgit2-sys archive checksum mismatch")
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != CHECKSUM:
        raise RuntimeError("libgit2-sys archive checksum mismatch")
    dest = deps / NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    patch = ROOT / "patches/deps/libgit2-sys-0.18.5-aros.patch"
    with tempfile.TemporaryDirectory(prefix="libgit2-check-", dir=dest.parent) as tmp:
        with tarfile.open(archive) as source:
            source.extractall(tmp, filter="data")
        expected = Path(tmp) / NAME
        subprocess.run(["git", "apply", str(patch)], cwd=expected, check=True)
        expected_files = snapshot(expected)
        if dest.exists():
            if snapshot(dest) != expected_files:
                raise RuntimeError(f"Generated libgit2 differs from pinned reconstruction: {dest}")
        else:
            shutil.copytree(expected, dest)
    return dest, {"archive_sha256": CHECKSUM, "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(), "files": expected_files}
