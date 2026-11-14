#!/usr/bin/env python3
"""Package the exact built executable with licences and corresponding source."""
import argparse,gzip,hashlib,io,json,tarfile,zipfile,subprocess,os
from pathlib import Path
import eza as port
p=argparse.ArgumentParser(description=__doc__);p.add_argument("--build-root",type=Path);p.add_argument("--output-name",required=True);args=p.parse_args()
r=port.ROOT;port.verify();b=args.build_root.resolve() if args.build_root else r/"build/v11";src=r/"work/eza"
identity=json.loads((b/"identity.json").read_text());binary=b/"target/x86_64-aros/release/eza"
if hashlib.sha256(binary.read_bytes()).hexdigest()!=identity["binary_sha256"]:raise RuntimeError("Executable differs from built identity")
if identity.get("eza_source")!=port.source_files(src):raise RuntimeError("Source changed since build; rebuild before packaging")
if port.std_identity(port.config()["toolchain"])!=identity["std_source"]:raise RuntimeError("Standard library source changed since build")
if port.source_files(port.dep_root(b)/"libc-dual")!=identity["libc_dual"]:raise RuntimeError("Generated libc changed since build")
# ZIP timestamps, source archive metadata and gzip header are deterministic.
buf=io.BytesIO()
with gzip.GzipFile(fileobj=buf,mode="wb",filename="",mtime=0) as gz:
 with tarfile.open(fileobj=gz,mode="w") as tar:
  for p in sorted(src.rglob("*")):
   rel=p.relative_to(src)
   if any(x in {".git","target"} for x in rel.parts):continue
   info=tar.gettarinfo(str(p),arcname="eza/"+str(rel));info.uid=info.gid=0;info.uname=info.gname="";info.mtime=0
   if p.is_file() and not p.is_symlink():
    with p.open("rb") as f:tar.addfile(info,f)
   else:tar.addfile(info)
files={"Eza/eza":binary.read_bytes(),"Eza/README.txt":(r/"packaging/README.txt").read_bytes(),"Eza/LICENSE.txt":(src/"LICENSE.txt").read_bytes(),"Eza/Source/eza-0.23.5-aros.tar.gz":buf.getvalue(),"Eza/Source/upstreams.json":(r/"upstreams.json").read_bytes()}
for p in (src/"LICENSES").rglob("*"):
 if p.is_file():files["Eza/LICENSES/"+str(p.relative_to(src/"LICENSES"))]=p.read_bytes()
for p in (r/"patches/eza").iterdir():files["Eza/Source/patches/"+p.name]=p.read_bytes()
# Retain linked dependency copyright/licence texts from the locked registry sources.
import tomllib
lock=tomllib.loads((src/"Cargo.lock").read_text())
cache=b/"cargo-home/registry/src"
for spec in lock["package"]:
 name,version=spec["name"],spec["version"]
 for root in cache.glob("*/"+name+"-"+version):
  for p in root.iterdir():
   if p.is_file() and p.name.upper().startswith(("LICENSE","LICENCE","COPYING","NOTICE","COPYRIGHT","AUTHORS")):
    files["Eza/Licenses/"+name+"-"+version+"/"+p.name]=p.read_bytes()
# The static zlib built by libz-sys (LIBZ_SYS_STATIC) carries its own notice.
if identity.get("build_env",{}).get("LIBZ_SYS_STATIC")!="1":raise RuntimeError("Build does not record the static zlib setting")
# The recorded setting is not proof: the SDK's libz.a stub would open z1.library.
if b"z1.library" in binary.read_bytes():raise RuntimeError("Executable still references z1.library; zlib is not static")
zlib=[p for p in cache.glob("*/libz-sys-*/src/zlib/LICENSE")]
if len(zlib)!=1:raise RuntimeError("Expected exactly one bundled zlib LICENSE in the build's registry sources")
files["Eza/Licenses/zlib/LICENSE"]=zlib[0].read_bytes()
# Patched local repository backend: include the exact corresponding source,
# licence texts (including nested bundled code), and reconstruction patch.
import git_deps
if identity.get("features") != ["git"]:raise RuntimeError("Build does not include the required Git backend")
git_crate=port.dep_root(b)/git_deps.NAME
if port.source_files(git_crate)!=identity["git_dependency"]["files"]:raise RuntimeError("Git dependency changed since build")
patch=r/"patches/deps/libgit2-sys-0.18.5-aros.patch"
if hashlib.sha256(patch.read_bytes()).hexdigest()!=identity["git_dependency"]["patch_sha256"]:raise RuntimeError("Git dependency patch changed since build")
files["Eza/Source/patches/deps/"+patch.name]=patch.read_bytes()
# The original checksum-pinned archive plus complete patched files makes the
# local backend reproducible without relying on Cargo registry retention.
git_archive=(b/"dependency-archives"/(git_deps.NAME+".crate")).read_bytes()
if hashlib.sha256(git_archive).hexdigest()!=identity["git_dependency"]["archive_sha256"]:raise RuntimeError("Git dependency archive changed since build")
files["Eza/Source/"+git_deps.NAME+".crate"]=git_archive
for p in git_crate.rglob("*"):
 if p.is_file():
  rel=str(p.relative_to(git_crate));files["Eza/Source/"+git_deps.NAME+"/"+rel]=p.read_bytes()
  if p.name.upper().startswith(("LICENSE","LICENCE","COPYING","COPYRIGHT","NOTICE","AUTHORS")):
   files["Eza/Licenses/"+git_deps.NAME+"/"+rel]=p.read_bytes()
# Non-registry runtime/entropy sources are compiled into the executable too.
for p in (port.dep_root(b)/"libc-dual").rglob("*"):
 if p.is_file() and p.name.upper().startswith(("LICENSE","LICENCE","COPYING","COPYRIGHT","NOTICE","HOST-LICENSE")):
  files["Eza/Licenses/libc-aros/"+str(p.relative_to(port.dep_root(b)/"libc-dual"))]=p.read_bytes()
cfg=port.config();notices=Path(os.environ.get("EZA_RUST_NOTICES",cfg.get("rust_notices","")))
if not (notices/"COPYRIGHT-library.html").is_file():raise RuntimeError("Set rust_notices in local.json (or EZA_RUST_NOTICES) to matching Rust runtime notices")
for p in [notices/"COPYRIGHT-library.html",*sorted((notices/"licenses").glob("*"))]:
 if p.is_file():files["Eza/Licenses/rust-runtime/"+p.name]=p.read_bytes()
archive=subprocess.check_output(["git","-C",cfg["rust_aros"],"archive",port.PIN,"LICENSE","std-groundwork/libc-aros","tools/libc-dual.py","x86_64-aros.json.in","limpet/vendor/sdk"])
files["Eza/Source/rust-aros-inputs.tar.gz"]=gzip.compress(archive,mtime=0)
# The Limpet presentation SDK is compiled into the executable (MIT).
files["Eza/Licenses/limpet-sdk/LICENSE.txt"]=subprocess.check_output(["git","-C",cfg["rust_aros"],"show",port.PIN+":limpet/vendor/LICENSE.txt"])
public={k:identity[k] for k in ["upstream","rust_aros","rust_inputs_sha256","rustc","target_sha256","binary_sha256","features","git_dependency"]}
public["std_source_files"]=identity["std_source"]["files"]
public["libc_dual"]=identity["libc_dual"]
files["Eza/BUILD.json"]=(json.dumps(public,indent=2)+"\n").encode()
files["Eza/Source/README.txt"]=b"Corresponding modified eza source is included. Original full pin and patch series are included. Runtime/compiler dependency: rust-aros e8e267dd0be6857d221b29b4ee8c7a5eaef92167 (helix-preview-1 tree), https://github.com/tomaszstaniak/rust-aros. See Cargo.lock for crate versions and checksums. No source copyright headers removed.\n"
dist=r/"dist";dist.mkdir(exist_ok=True);dest=dist/args.output_name
# Delivered archives are never replaced; SHA256SUMS only gains a line.
if dest.exists():raise RuntimeError(f"{dest} exists; choose a new --output-name")
with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,data in sorted(files.items()):
  i=zipfile.ZipInfo(name,(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=((0o100755 if name=="Eza/eza" else 0o100644)<<16);z.writestr(i,data)
with zipfile.ZipFile(dest) as z:
 if z.testzip() is not None or z.read("Eza/eza")!=binary.read_bytes():raise RuntimeError("ZIP integrity mismatch")
sha=hashlib.sha256(dest.read_bytes()).hexdigest();sums=dist/"SHA256SUMS"
with sums.open("a") as f:f.write(sha+"  "+dest.name+"\n")
print(dest);print(sha)
