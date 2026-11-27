#!/usr/bin/env python3
"""Assemble dist/Eza-<VERSION>-r<REVISION>-<TARGET>.zip, an apkg package.

    release.py TARGET REVISION

ABIv11: the executable, licences and corresponding source of the accepted archive made by
package.py (dist/Eza-0.23.5-aros-candidate11-abiv11.zip), unchanged, with the release README.
Mainline targets: the executable of build_target.py with its build record; the same eza source,
patches and licence texts, plus the platform patches and the build script used.

apkg-pack (arospkg) writes the archive with the catalogue manifest and checks it. Archives in
dist/ are never replaced; SHA256SUMS only gains lines.
"""
import hashlib, json, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.23.5"
BASE = "Eza-0.23.5-aros-candidate11-abiv11.zip"
BASE_SHA256 = "4101b839"
EPOCH = 315532800
TARGETS = {
    "aros-x86_64-abiv11-pc": {"arch": "x86_64", "abi": "v11", "system": "AROS One and other ABIv11 systems on PC",
                              "requires": ["crt.library", "m.library", "stdlib.library"]},
    "aros-x86_64-abiv1-pc": {"arch": "x86_64", "abi": "v1", "system": "mainline AROS (ABIv1) on PC",
                             "requires": ["posixc.library", "stdc.library", "stdcio.library"],
                             "notes": ["Needs an AROS nightly of 2026-11-24 or later; for earlier nightlies use revision 1 from the project page."]},
    "aros-aarch64-abiv1-raspi": {"arch": "aarch64", "abi": "v1", "system": "native AROS on the Raspberry Pi (ABIv1)",
                                 "requires": ["posixc.library", "stdc.library", "stdcio.library"],
                                 "notes": ["Needs an AROS nightly of 2026-11-24 or later; for earlier nightlies use revision 1 from the project page.",
                                           "Native Raspberry Pi build (mainline ABIv1); not for PomAROS. "
                                           "Tested under QEMU (raspi3b), not on a real Raspberry Pi."]},
}


def manifest(target, revision):
    t = TARGETS[target]
    lines = ['id              = "eza"', f'version         = "{VERSION}"', f"revision        = {revision}",
             'summary         = "A modern replacement for List and Dir: colours, icons, tree view, Git status"',
             'category        = "utility/shell"', 'license         = "EUPL-1.2"', 'kind            = "app"',
             f'arch            = "{t["arch"]}"', f'abi             = "{t["abi"]}"', 'subdir          = "Eza"',
             "depends         = []", "depends_checked = true", ""]
    notes = ["eza lists files in Limpet 0.7.0 or later (apkg install limpet); the standard Shell window gets help and --version only."] + t.get("notes", [])
    lines += ["post_install_notes = ["] + [f"  {json.dumps(n)}," for n in notes] + ["]", ""]
    for lib in t["requires"]:
        lines += ["[[requires_system]]", 'type = "library"', f'id   = "{lib}"', ""]
    lines += ["[launch]", 'executable = "eza"', 'mode       = "shell"', ""]
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in TARGETS or not sys.argv[2].isdigit():
        raise SystemExit(__doc__)
    target, revision = sys.argv[1], int(sys.argv[2])
    name = f"{VERSION}-r{revision}"
    dist = ROOT / "dist"
    out = dist / f"Eza-{name}-{target}.zip"
    if out.exists():
        raise RuntimeError(f"{out} exists; delivered archives are not replaced")
    base = dist / BASE
    if not hashlib.sha256(base.read_bytes()).hexdigest().startswith(BASE_SHA256):
        raise RuntimeError(f"{base} is not the accepted archive")
    with tempfile.TemporaryDirectory(prefix="eza-release-") as d:
        parent = Path(d)
        with zipfile.ZipFile(base) as z:
            z.extractall(parent)
        drawer = parent / "Eza"
        if target == "aros-x86_64-abiv11-pc":
            binary = (drawer / "eza").read_bytes()
            shutil.move(drawer / "BUILD.json", drawer / "Source" / "BUILD.json")
        else:
            build = ROOT / "build" / target
            identity = json.loads((build / "identity.json").read_text())
            binary = (build / "eza").read_bytes()
            if hashlib.sha256(binary).hexdigest() != identity["binary_sha256"]:
                raise RuntimeError("executable differs from its build record")
            import eza as port
            if identity["eza_source"] != port.source_files(ROOT / "work/eza"):
                raise RuntimeError("source changed since the build")
            (drawer / "eza").write_bytes(binary)
            (drawer / "BUILD.json").unlink()
            source = drawer / "Source"
            # The ABIv11 recipe's inputs do not describe this build.
            (source / "rust-aros-inputs.tar.gz").unlink()
            public = {k: identity[k] for k in ("target", "rust_aros_commit", "rustc", "gcc", "libc_version", "libc_patches",
                                               "binary_sha256", "bytes", "features", "upstream", "git_dependency",
                                               "target_json_sha256", "presentation_sdk_pin") if k in identity}
            public["sdk"] = Path(identity["sdk"]).parent.name
            (source / "BUILD.json").write_text(json.dumps(public, indent=2) + "\n")
            shutil.copy2(ROOT / "scripts" / "build_target.py", source / "build_target.py")
            shutil.copytree(ROOT / "patches/platform/libc-aros", source / "patches/platform/libc-aros")
            if target.endswith("-raspi"):
                shutil.copy2(ROOT / "patches/deps/libgit2-sys-0.18.5-aros-process.patch", source / "patches" / "deps")
            (source / "README.txt").write_text(
                "Corresponding modified eza source is included (eza-0.23.5-aros.tar.gz), with the original pin and the patch\n"
                "series. This build was made by build_target.py with rust-aros " + identity["rust_aros_commit"] + "\n"
                "(https://github.com/tomaszstaniak/rust-aros): its target profile and libc-aros with the patches under\n"
                "patches/platform. BUILD.json is the build record. See Cargo.lock in the source for crate versions.\n")
        (drawer / "eza").chmod(0o755)
        text = (ROOT / "packaging" / "README.txt").read_text()
        pi = ("- This build runs on the native Raspberry Pi system. It was tested under\n  QEMU's Pi model, not on a real Raspberry Pi.\n"
              if target.endswith("-raspi") else "")
        (drawer / "README.txt").write_text(text.replace("@VERSION@", name).replace("@TARGET@", target)
                                           .replace("@SYSTEM@", TARGETS[target]["system"]).replace("@PI@\n", pi))
        # What TAB offers after "eza" in Limpet: Completions/eza beside the program.
        (drawer / "Completions").mkdir()
        shutil.copy2(ROOT / "packaging" / "Completions" / "eza", drawer / "Completions" / "eza")
        (parent / "Eza.arospkg.toml").write_text(manifest(target, revision))
        apkg = json.loads((ROOT / "local.json").read_text()).get("apkg_pack")
        if not apkg or not Path(apkg).is_file():
            raise RuntimeError("local.json: set apkg_pack to arospkg's tools/apkg-pack")
        dist.mkdir(exist_ok=True)
        subprocess.run([sys.executable, apkg, "build", drawer, "--output", out, "--epoch", str(EPOCH)], check=True)
        subprocess.run([sys.executable, apkg, "check", out], check=True)
    with zipfile.ZipFile(out) as z:
        if z.testzip() is not None or z.read("Eza/eza") != binary:
            out.unlink()
            raise RuntimeError("archive does not hold the built executable")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    with (dist / "SHA256SUMS").open("a") as f:
        f.write(f"{sha}  {out.name}\n")
    print(f"{out} {sha}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
        print(f"release: {e}", file=sys.stderr)
        sys.exit(1)
