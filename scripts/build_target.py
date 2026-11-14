#!/usr/bin/env python3
"""Build eza for mainline AROS x86_64 (ABIv1). The Raspberry Pi target (AArch64 ABIv1) is work
in progress: its std and libc differ, and that build does not complete yet.

The ABIv11 executable is built by eza.py (byte-reproducible recipe). The two mainline targets
follow the recipe the other Rust ports use with rust-aros: its target profile, libc-aros as the
crates.io libc, and on AArch64 the C bridge of the std PAL linked before the SDK's libraries.

    python3 scripts/build_target.py --target aros-x86_64-abiv1-pc --local local.v1.json
    python3 scripts/build_target.py --target aros-aarch64-abiv1-raspi --local local.raspi.json

The local file names: aros_gcc, aros_ar, aros_sdk, rust_aros, rust_aros_commit, toolchain,
and for AArch64 pomaros_hosted (clean checkout of the commit below) and glue_patches
(directory with a series file). Output: build/<target>/eza and build/<target>/identity.json.
"""
import argparse, hashlib, io, json, os, re, shlex, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eza as port
import git_deps

ROOT = port.ROOT
RUSTC = "rustc 1.100.0-nightly (0dfb098f3 2026-08-31)"
POMAROS_HOSTED = "3bc9359d439f9fb5655cf48924413ffe670931cc"
GLUE = ("aros_fs_glue", "aros_thread_glue", "aros_sync_glue", "aros_env_glue",
        "aros_process_glue", "aros_proc_glue", "aros_net_glue")
# target -> rust-aros profile, Cargo target name, (EI_ABIVERSION, e_machine)
TARGETS = {
    "aros-x86_64-abiv1-pc": ("x86_64-v1-pc", (1, 62)),
    "aros-aarch64-abiv1-raspi": ("aarch64-v1-raspi", (1, 183)),
}


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def out(cmd, **kw):
    return subprocess.check_output([str(c) for c in cmd], **kw)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tool(cfg, name):
    driver = cfg["aros_gcc"]
    for suffix in ("-gcc", "-clang"):
        if driver.endswith(suffix):
            return driver[: -len(suffix)] + "-" + name
    raise RuntimeError(f"cannot derive {name} from {driver}")


def build_glue(cfg, root):
    checkout = Path(cfg["pomaros_hosted"])
    if out(["git", "-C", checkout, "rev-parse", "HEAD"], text=True).strip() != POMAROS_HOSTED or out(["git", "-C", checkout, "status", "--porcelain"], text=True):
        raise RuntimeError(f"{checkout} must be a clean checkout of {POMAROS_HOSTED}")
    patch_dir = ROOT / cfg["glue_patches"]
    patches = [patch_dir / n for n in (patch_dir / "series").read_text().split()]
    dest = root / "aros-glue"
    if dest.exists():
        shutil.rmtree(dest)
    src = dest / "src/hosted/rust"
    src.mkdir(parents=True)
    for name in GLUE:
        shutil.copy2(checkout / "hosted/rust" / f"{name}.c", src / f"{name}.c")
    for patch in patches:
        run(["patch", "--quiet", "-p1", "-i", patch], cwd=dest / "src")
    for name in GLUE:
        run([cfg["aros_gcc"], f"--sysroot={cfg['aros_sdk']}", "-O2", "-I", checkout / "hosted/rust", "-c", src / f"{name}.c", "-o", dest / f"{name}.o"])
    return dest, {"pomaros_hosted_commit": POMAROS_HOSTED, "patches": {p.name: sha(p) for p in patches},
                  "objects": {f"{n}.o": sha(dest / f"{n}.o") for n in GLUE}}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, choices=sorted(TARGETS))
    p.add_argument("--local", required=True, type=Path)
    a = p.parse_args()
    cfg = json.loads(a.local.read_text())
    profile, elf = TARGETS[a.target]
    raspi = profile.startswith("aarch64")
    port.verify()
    if out(["rustc", "+" + cfg["toolchain"], "--version"], text=True).strip() != RUSTC:
        raise RuntimeError(f"toolchain {cfg['toolchain']} is not `{RUSTC}`")
    root = ROOT / "build" / a.target
    root.mkdir(parents=True, exist_ok=True)
    work = ROOT / "work/eza"
    src = root / "src"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(work, src, symlinks=True, ignore=shutil.ignore_patterns(".git", "target"))
    rust, commit = Path(cfg["rust_aros"]), cfg["rust_aros_commit"]
    sysroot = Path(out(["rustc", "+" + cfg["toolchain"], "--print", "sysroot"], text=True).strip())
    record = {"target": a.target, "rust_aros_commit": commit, "toolchain": cfg["toolchain"], "rustc": RUSTC}
    if raspi:
        libc = sysroot / "lib/rustlib/src/rust/library/libc-aros"
        if 'Ok("aarch64") { return; }' not in (libc / "build.rs").read_text():
            raise RuntimeError(f"{libc} is not the common sysroot's aarch64 adaptation")
    else:
        libc = root / f"libc-aros-{commit[:12]}"
        if libc.exists():
            shutil.rmtree(libc)
        with tempfile.TemporaryDirectory(prefix="libc-", dir=root) as tmp:
            with tarfile.open(fileobj=io.BytesIO(out(["git", "-C", rust, "archive", "--format=tar", commit, "std-groundwork/libc-aros"]))) as tar:
                tar.extractall(tmp, filter="data")
            staged = Path(tmp) / "std-groundwork/libc-aros"
            patch_dir = ROOT / cfg["libc_patches"]
            for name in (patch_dir / "series").read_text().split():
                run(["patch", "--quiet", "-p1", "-i", patch_dir / name], cwd=staged)
                record.setdefault("libc_patches", {})[name] = sha(patch_dir / name)
            staged.rename(libc)
    record["libc_aros"] = port.source_files(libc)
    # Build scripts and their dependencies (cc's jobserver) are compiled for the host with the
    # same crates.io libc entry: the dual crate is libc-aros for AROS and the registry libc
    # elsewhere, as in the ABIv11 build.
    cargo_home = root / "cargo-home"
    cache = cargo_home / "registry/cache/index.crates.io-1949cf8c6b5b557f"
    cache.mkdir(parents=True, exist_ok=True)
    crate = cache / "libc-0.2.189.crate"
    if not crate.exists():
        import urllib.request
        data = urllib.request.urlopen("https://static.crates.io/crates/libc/libc-0.2.189.crate", timeout=60).read()
        if hashlib.sha256(data).hexdigest() != "3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2":
            raise RuntimeError("libc archive checksum mismatch")
        crate.write_bytes(data)
    with tempfile.TemporaryDirectory(prefix="dual-", dir=root) as tmp:
        with tarfile.open(fileobj=io.BytesIO(out(["git", "-C", rust, "archive", "--format=tar", commit, "tools/libc-dual.py"]))) as tar:
            tar.extractall(tmp, filter="data")
        dual = root / "libc-dual"
        if dual.exists():
            shutil.rmtree(dual)
        run([sys.executable, Path(tmp) / "tools/libc-dual.py", libc, dual, "--cargo-home", cargo_home])
    aros_libc, libc = libc, dual
    # The presentation SDK compiled into eza: the pinned copy the ABIv11 build uses.
    with tempfile.TemporaryDirectory(prefix="sdk-", dir=root) as tmp:
        with tarfile.open(fileobj=io.BytesIO(out(["git", "-C", rust, "archive", "--format=tar", port.PIN, "limpet/vendor/sdk"]))) as tar:
            tar.extractall(tmp, filter="data")
        sdk = root / "limpet-sdk"
        if sdk.exists():
            shutil.rmtree(sdk)
        (Path(tmp) / "limpet/vendor/sdk").rename(sdk)
    deps = root / "deps"
    deps.mkdir(exist_ok=True)
    git_crate, git_identity = git_deps.stage(root, deps, port.source_files)
    if raspi:
        # The Pi SDK declares neither fork() nor sigwait(), and Clang refuses the implicit
        # declarations: libgit2's helper-program code is compiled out there (never reached in the
        # local-repository build).
        extra = ROOT / "patches/deps/libgit2-sys-0.18.5-aros-process.patch"
        copy = deps / (git_deps.NAME + "-raspi")
        if copy.exists():
            shutil.rmtree(copy)
        shutil.copytree(git_crate, copy)
        run(["patch", "--quiet", "-p1", "-i", extra], cwd=copy)
        git_crate = copy
        git_identity["extra_patch_sha256"] = sha(extra)
    target = json.loads(out(["git", "-C", rust, "show", f"{commit}:profiles/{profile}.json"]))
    if raspi:
        glue_dir, record["glue"] = build_glue(cfg, root)
        linker = root / "aarch64-aros-linker"
        linker.write_text("#!/bin/sh\nset -e\nexec " + shlex.quote(cfg["aros_gcc"]) + ' "$@" -Wl,--no-gc-sections\n')
        linker.chmod(0o755)
        target["linker"] = str(linker)
        target["no-default-libraries"] = False
        target["pre-link-args"] = {"gnu-cc": [f"--sysroot={cfg['aros_sdk']}"] + [str(glue_dir / f"{n}.o") for n in GLUE]}
    else:
        target["linker"] = cfg["aros_gcc"]
        target["pre-link-args"]["gnu-cc"] = [f"--sysroot={cfg['aros_sdk']}"]
    target["late-link-args"] = {"gnu-cc": ["-lpthread"]}
    # Build scripts (libgit2-sys) recognise AROS by the target name.
    tname = ("aarch64" if raspi else "x86_64") + "-aros"
    target_json = root / f"{tname}.json"
    target_json.write_text(json.dumps(target, indent=2) + "\n")
    triple = tname.replace("-", "_")
    cflags = [f"--sysroot={cfg['aros_sdk']}", "-fno-pic", f"-ffile-prefix-map={root}=/eza-build"] + ([] if raspi else ["-mcmodel=large"])
    env = dict(os.environ, LIBZ_SYS_STATIC="1", CARGO_HOME=str(cargo_home), CARGO_TARGET_DIR=str(root / "target"),
               AROS_GCC=cfg["aros_gcc"], AROS_AR=cfg["aros_ar"], AROS_SDK=cfg["aros_sdk"], EZA_LIMPET_SDK=str(sdk))
    env.update({f"CC_{triple}": cfg["aros_gcc"], f"AR_{triple}": cfg["aros_ar"], f"CFLAGS_{triple}": " ".join(cflags)})
    for name in ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_RUSTFLAGS"):
        env.pop(name, None)
    flags = ["-Cpanic=abort", f"--remap-path-prefix={root}=/eza-build", f"--remap-path-prefix={libc}=/libc-aros", f"--remap-path-prefix={aros_libc}=/libc-aros",
             f"--remap-path-prefix={sysroot}=/rust"]
    patches = ["--config", "patch.crates-io.libc.path=" + json.dumps(str(libc)),
               "--config", "patch.crates-io.libgit2-sys.path=" + json.dumps(str(git_crate))]
    version = re.search(r'^version = "([^"]+)"', (libc / "Cargo.toml").read_text(), re.M).group(1)
    for old in sorted(set(re.findall(r'name = "libc"\nversion = "([^"]+)"', (src / "Cargo.lock").read_text()))):
        if old != version:
            run(["cargo", "+" + cfg["toolchain"], "update", "--manifest-path", src / "Cargo.toml", *patches, "-p", f"libc@{old}", "--precise", version], env=env)
    record["libc_version"] = version
    cmd = ["cargo", "+" + cfg["toolchain"], "build", "--release", "--no-default-features", "--features", "git",
           "--target", target_json, "-Zbuild-std=std,panic_abort", "-Zjson-target-spec",
           "--config", "profile.release.strip=false", "--config", "build.rustflags=" + json.dumps(flags), *patches]
    log = root / "build.log"
    with log.open("wb") as f:
        result = subprocess.run([str(c) for c in cmd], cwd=src, env=env, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"build failed; see {log}")
    binary = root / "target" / tname / "release" / "eza"
    undefined = out([tool(cfg, "nm"), "-u", binary], text=True).split()
    if undefined:
        raise RuntimeError(f"undefined symbols: {undefined[:10]}")
    head = binary.read_bytes()[:20]
    if head[:8] != bytes.fromhex("7f454c460201010f") or head[8] != elf[0] or int.from_bytes(head[18:20], "little") != elf[1]:
        raise RuntimeError(f"{binary} is not an AROS ELF64 object for {a.target}: {head.hex()}")
    if b"z1.library" in binary.read_bytes():
        raise RuntimeError("executable references z1.library; zlib is not static")
    shutil.copy2(binary, root / "eza")
    record.update(binary_sha256=sha(binary), bytes=binary.stat().st_size, eza_source=port.source_files(work),
                  upstream=port.manifest(), git_dependency={k: v for k, v in git_identity.items() if k != "files"},
                  target_json_sha256=sha(target_json), features=["git"], presentation_sdk_pin=port.PIN,
                  gcc=out([cfg["aros_gcc"], "--version"], text=True).splitlines()[0], sdk=cfg["aros_sdk"])
    (root / "identity.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"binary": str(root / "eza"), "sha256": record["binary_sha256"], "bytes": record["bytes"]}, indent=1))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"eza-port: {e}", file=sys.stderr)
        sys.exit(1)
