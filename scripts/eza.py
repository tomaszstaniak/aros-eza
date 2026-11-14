#!/usr/bin/env python3
"""Pinned source reconstruction and ABIv11 build. Never resets existing sources."""
import argparse, hashlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PIN="e8e267dd0be6857d221b29b4ee8c7a5eaef92167"
def run(args,**kwargs):
 return subprocess.run([str(x) for x in args],check=True,**kwargs)
def manifest():return json.loads((ROOT/"upstreams.json").read_text())["repositories"]["eza"]
def check_upstream():
 spec=manifest(); p=ROOT/"upstream/eza"
 head=subprocess.check_output(["git","-C",str(p),"rev-parse","HEAD"],text=True).strip()
 status=subprocess.check_output(["git","-C",str(p),"status","--porcelain","--untracked-files=all"],text=True)
 if head!=spec["commit"] or status:raise RuntimeError("upstream/eza must be clean at the pinned commit")
 return p
def reconstruct(dest):
 upstream=check_upstream()
 if dest.exists():raise RuntimeError(f"Refusing to replace {dest}; preserve files and Git history first")
 run(["git","clone","--quiet",upstream,dest]);run(["git","-C",dest,"checkout","--quiet",manifest()["commit"]])
 for name in (ROOT/"patches/eza/series").read_text().splitlines():
  if name and not name.startswith("#"):run(["git","-C",dest,"apply",ROOT/"patches/eza"/name])
def source_files(root):
 return {str(p.relative_to(root)):[hashlib.sha256(p.read_bytes()).hexdigest(),bool(p.stat().st_mode&0o111)] for p in root.rglob("*") if p.is_file() and not any(x in {".git","target"} for x in p.relative_to(root).parts)}
def verify():
 with tempfile.TemporaryDirectory(prefix="eza-reproduce-") as d:
  dest=Path(d)/"eza";reconstruct(dest)
  if source_files(dest)!=source_files(ROOT/"work/eza"):raise RuntimeError("work/eza differs from isolated reconstruction; save all source deltas")
 print("Source contents and executable modes match isolated reconstruction")
def config():
 local=ROOT/"local.json";cfg=json.loads(local.read_text()) if local.exists() else {}
 for key in ["aros_gcc","aros_ar","aros_sdk","rust_aros","toolchain"]:
  cfg[key]=os.environ.get("EZA_"+key.upper(),cfg.get(key))
  if not cfg[key]:raise RuntimeError(f"Set EZA_{key.upper()} or copy local.example.json to local.json")
 return cfg
def stage_pin(dest, archive):
 with tempfile.TemporaryDirectory(prefix="eza-pin-check-") as d:
  expected=Path(d)/"source";expected.mkdir()
  with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(expected,filter="data")
  if dest.exists():
   if source_files(dest)!=source_files(expected):raise RuntimeError(f"Pinned build inputs changed at {dest}; preserve local files before recovery")
  else:shutil.copytree(expected,dest)

def stage_libc(rt, libc, cargo_home):
 # Regenerate independently on every invocation: an identity file cannot prove
 # that a cached generated crate still matches the pinned generator inputs.
 with tempfile.TemporaryDirectory(prefix="eza-libc-check-",dir=libc.parent) as d:
  expected=Path(d)/"libc"
  run([sys.executable,rt/"tools/libc-dual.py",rt/"std-groundwork/libc-aros",expected,"--cargo-home",cargo_home])
  if libc.exists():
   if source_files(libc)!=source_files(expected):raise RuntimeError(f"Generated libc differs from pinned reconstruction: {libc}")
  else:shutil.copytree(expected,libc)
 return source_files(libc)

def std_identity(toolchain):
 sysroot=Path(subprocess.check_output(["rustc","+"+toolchain,"--print","sysroot"],text=True).strip()).resolve()
 library=sysroot/"lib/rustlib/src/rust/library"
 if not (library/"std/src/lib.rs").is_file():raise RuntimeError(f"Missing build-std source at {library}")
 return {"sysroot":str(sysroot),"library":str(library.resolve()),"files":source_files(library)}

def dep_root(b):return b/"src/target/aros-deps"
def build(source=None,build_root=None):
 cfg=config();verify()
 source=Path(source) if source else ROOT/"work/eza"
 if source_files(source)!=source_files(ROOT/"work/eza"):raise RuntimeError("Selected build source differs from verified reconstruction")
 b=Path(build_root).resolve() if build_root else ROOT/"build/v11";b.mkdir(parents=True,exist_ok=True)
 # Cargo hashes a path dependency's absolute location into every dependent
 # crate's metadata unless it lies inside the workspace. Build a private copy
 # of the source with the generated libc and libgit2 under its target/, so
 # two independent roots give the same symbols and the same executable.
 copy=b/"src"
 if copy.exists():
  if source_files(copy)!=source_files(source):raise RuntimeError(f"Build source copy differs: {copy}")
 else:shutil.copytree(source,copy,symlinks=True,ignore=shutil.ignore_patterns(".git","target"))
 source=copy;deps=dep_root(b);deps.mkdir(parents=True,exist_ok=True)
 std=std_identity(cfg["toolchain"])
 rust=Path(cfg["rust_aros"]);rt=b/("rust-aros-"+PIN[:12])
 archive=subprocess.check_output(["git","-C",str(rust),"archive",PIN,"std-groundwork/libc-aros","tools/libc-dual.py","x86_64-aros.json.in","limpet/vendor/sdk"])
 stage_pin(rt,archive)
 sdk=rt/"limpet/vendor/sdk"
 cargo_home=b/"cargo-home";cargo_home.mkdir(exist_ok=True)
 # Bootstrap only the immutable libc archive needed by the dual-libc tool.
 if not list(cargo_home.glob("registry/cache/*/libc-0.2.189.crate")):
  import urllib.request
  cache=cargo_home/"registry/cache/index.crates.io-1949cf8c6b5b557f";cache.mkdir(parents=True,exist_ok=True)
  data=urllib.request.urlopen("https://static.crates.io/crates/libc/libc-0.2.189.crate",timeout=60).read()
  if hashlib.sha256(data).hexdigest()!="3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2":raise RuntimeError("libc archive checksum mismatch")
  (cache/"libc-0.2.189.crate").write_bytes(data)
 libc=deps/"libc-dual"
 libc_files=stage_libc(rt,libc,cargo_home)
 # build-std resolves std's libc inside the sysroot's library workspace, so its
 # absolute path is hashed into std and every crate above it. Each build still
 # generates and checks its own copy; the patch then names one immutable copy
 # per content hash, shared read-only like the target specification.
 shared=ROOT/"build/targets"/("libc-dual-"+hashlib.sha256(json.dumps(libc_files,sort_keys=True).encode()).hexdigest())
 if shared.exists():
  if source_files(shared)!=libc_files:raise RuntimeError(f"Shared generated libc changed: {shared}")
 else:
  tmp=shared.with_name(shared.name+".tmp."+str(os.getpid()));shutil.copytree(libc,tmp);os.replace(tmp,shared)
 import git_deps
 git_crate,git_identity=git_deps.stage(b,deps,source_files)
 spec=(rt/"x86_64-aros.json.in").read_text().replace("@AROS_GCC@",cfg["aros_gcc"]).replace("@AROS_SDK@",cfg["aros_sdk"]).replace("@AROS_EXTRA_LIBS@",', "-lpthread"').encode()
 # Cargo hashes the absolute path of a JSON target into every crate, core
 # included, and this rustc no longer reads RUST_TARGET_PATH. Keep one
 # immutable copy per content hash, shared read-only like the toolchain.
 target=ROOT/"build/targets"/hashlib.sha256(spec).hexdigest()/"x86_64-aros.json"
 if target.exists():
  if target.read_bytes()!=spec:raise RuntimeError(f"Target specification changed: {target}")
 else:
  target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix(".tmp."+str(os.getpid()));tmp.write_bytes(spec);os.replace(tmp,target)
 # libz-sys otherwise links the SDK libz.a, a stub that opens z1.library at
 # startup; ship the bundled static zlib instead.
 env=dict(os.environ,LIBZ_SYS_STATIC="1",CARGO_HOME=str(cargo_home),CARGO_TARGET_DIR=str(b/"target"),AROS_GCC=cfg["aros_gcc"],AROS_SDK=cfg["aros_sdk"],AROS_AR=cfg["aros_ar"],EZA_LIMPET_SDK=str(sdk),CC_x86_64_aros=cfg["aros_gcc"],AR_x86_64_aros=cfg["aros_ar"],CFLAGS_x86_64_aros=f"--sysroot={cfg['aros_sdk']} -fno-PIC -ffile-prefix-map={b}=/eza-build")
 # Panic locations and C __FILE__ strings embed the build root (Cargo home,
 # source copy, generated libc, patched libgit2). trim-paths rewrites Rust
 # paths with a fixed setting; a root-specific --remap-path-prefix would enter
 # every crate's metadata hash. C sources get -ffile-prefix-map via CFLAGS.
 cmd=["cargo","+"+cfg["toolchain"],"build","--release","--locked","--no-default-features","--features","git","--target",target,"-Zbuild-std=std,panic_abort","-Zjson-target-spec","--config","profile.release.strip=false","-Ztrim-paths","--config",'profile.release.trim-paths="all"',"--config",'build.rustflags=["-Cpanic=abort"]',"--config","patch.crates-io.libc.path="+json.dumps(str(shared)),"--config","patch.crates-io.libgit2-sys.path="+json.dumps(str(git_crate))]
 run(cmd,cwd=source,env=env)
 binary=b/"target/x86_64-aros/release/eza"
 if std_identity(cfg["toolchain"])!=std:raise RuntimeError("build-std source changed during build")
 if source_files(libc)!=libc_files or source_files(shared)!=libc_files:raise RuntimeError("Generated libc changed during build")
 if source_files(git_crate)!=git_identity["files"]:raise RuntimeError("Generated libgit2 changed during build")
 identity={"build_env":{"LIBZ_SYS_STATIC":env["LIBZ_SYS_STATIC"]},"git_dependency":git_identity,"features":["git"],"build_root":str(b),"std_source":std,"libc_dual":libc_files,"eza_source":source_files(ROOT/"work/eza"),"upstream":manifest(),"rust_aros":PIN,"rust_inputs_sha256":hashlib.sha256(archive).hexdigest(),"presentation_sdk":source_files(sdk),"rustc":subprocess.check_output(["rustc","+"+cfg["toolchain"],"--version","--verbose"],text=True),"config":cfg,"target_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest()}
 (b/"identity.json").write_text(json.dumps(identity,indent=2)+"\n")
def probes(b):
 """Native test programs, built from the same inputs as the executable in b."""
 cfg=config();identity=json.loads((b/"identity.json").read_text());out=b/"probes";out.mkdir(exist_ok=True)
 gcc=[cfg["aros_gcc"],"--sysroot="+cfg["aros_sdk"],"-O2"]
 for name in ["acceptance","dirprobe"]:run(gcc+[ROOT/"tests/native"/(name+".c"),"-o",out/name])
 # git_status links the very libgit2 and zlib archives linked into eza.
 build=b/"target/x86_64-aros/release/build"
 git=list(build.glob("libgit2-sys/*/out/build/libgit2.a"));zlib=list(build.glob("libz-sys/*/out/lib/libz.a"))
 if len(git)!=1 or len(zlib)!=1:raise RuntimeError("Expected one libgit2.a and one libz.a in "+str(build))
 run(gcc+["-I",git[0].parent.parent/"include",ROOT/"tests/native/git_status.c",git[0],zlib[0],"-lpthread","-o",out/"git_status"])
 run(gcc+["-I",git[0].parent.parent/"include",ROOT/"tests/native/git_discover.c",git[0],zlib[0],"-lpthread","-o",out/"git_discover"])
 # The Rust probe uses eza's target, build-std flags and the same shared libc.
 crate=out/"dirprobe-rust";(crate/"src").mkdir(parents=True,exist_ok=True)
 (crate/"Cargo.toml").write_text('[package]\nname="dirprobe-rust"\nversion="0.1.0"\nedition="2024"\n[workspace]\n')
 shutil.copyfile(ROOT/"tests/native/dirprobe.rs",crate/"src/main.rs")
 shared=ROOT/"build/targets"/("libc-dual-"+hashlib.sha256(json.dumps(identity["libc_dual"],sort_keys=True).encode()).hexdigest())
 target=ROOT/"build/targets"/identity["target_sha256"]/"x86_64-aros.json"
 if hashlib.sha256(target.read_bytes()).hexdigest()!=identity["target_sha256"]:raise RuntimeError("Target specification differs from the build")
 if source_files(shared)!=identity["libc_dual"]:raise RuntimeError("Shared generated libc differs from the build")
 env=dict(os.environ,CARGO_HOME=str(b/"cargo-home"),CARGO_TARGET_DIR=str(out/"target"),AROS_GCC=cfg["aros_gcc"],AROS_SDK=cfg["aros_sdk"],AROS_AR=cfg["aros_ar"],CC_x86_64_aros=cfg["aros_gcc"],AR_x86_64_aros=cfg["aros_ar"],CFLAGS_x86_64_aros=f"--sysroot={cfg['aros_sdk']} -fno-PIC")
 run(["cargo","+"+cfg["toolchain"],"build","--release","--target",target,"-Zbuild-std=std,panic_abort","-Zjson-target-spec","--config","profile.release.strip=false","--config",'build.rustflags=["-Cpanic=abort"]',"--config","patch.crates-io.libc.path="+json.dumps(str(shared))],cwd=crate,env=env)
 shutil.copyfile(out/"target/x86_64-aros/release/dirprobe-rust",out/"dirprobe-rust-bin")
 sums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/"acceptance",out/"dirprobe",out/"git_status",out/"git_discover",out/"dirprobe-rust-bin"]}
 (out/"probes.json").write_text(json.dumps({"eza_binary_sha256":identity["binary_sha256"],"probes":sums},indent=2)+"\n");print(json.dumps(sums,indent=1))
def tests():
 run([sys.executable,"-m","unittest","discover","-s",ROOT/"tests"])
 with tempfile.TemporaryDirectory(prefix="eza-tests-") as d:
  exe=Path(d)/"policy-tests";run(["rustc","--test",ROOT/"work/eza/src/aros_policy.rs","-o",exe]);run([exe])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("action",choices=["materialize","verify","build","rebuild","native","test"]);p.add_argument("--build-root",type=Path);a=p.parse_args()
 if a.action=="materialize":reconstruct(ROOT/"work/eza")
 elif a.action=="verify":verify()
 elif a.action=="build":build(build_root=a.build_root)
 elif a.action=="rebuild":
  if a.build_root is None:raise RuntimeError("rebuild requires --build-root pointing to a new independent directory")
  if a.build_root.exists():raise RuntimeError("rebuild requires a new build root (independent Cargo cache and target)")
  with tempfile.TemporaryDirectory(prefix="eza-build-reproduce-") as d:
   source=Path(d)/"eza";reconstruct(source);build(source,a.build_root)
 elif a.action=="native":
  if a.build_root is None:raise RuntimeError("native requires --build-root of a completed build")
  probes(a.build_root.resolve())
 else:tests()
if __name__=="__main__":
 try:main()
 except (RuntimeError,subprocess.CalledProcessError) as e:print(f"eza-port: {e}",file=sys.stderr);sys.exit(1)
