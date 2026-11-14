#!/usr/bin/env python3
# SPDX-License-Identifier: EUPL-1.2
"""Exercise retained directory handles with a real CLI under a low FD limit."""
import os,resource,subprocess,sys,tempfile
from pathlib import Path
binary=Path(sys.argv[1]).resolve()
def limited():
 resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
with tempfile.TemporaryDirectory(prefix="eza-directory-lifetime-") as tmp:
 root=Path(tmp);wide=root/"wide";wide.mkdir()
 for i in range(160):
  child=wide/f"dir{i:03d}";child.mkdir();(child/f"leaf{i:03d}").write_text("x")
 deep=root/"deep";deep.mkdir();p=deep
 for _ in range(72):p=p/"d";p.mkdir()
 (p/"deep-leaf").write_text("x")
 for name,path in [("wide",wide),("deep",deep)]:
  result=subprocess.run([str(binary),"-Tl","--color=never",str(path)],capture_output=True,text=True,preexec_fn=limited,env=dict(os.environ,EZA_ICONS="never"))
  assert result.returncode==0,(name,result.returncode,result.stderr)
  if name=="wide":
   for i in range(160):assert result.stdout.count(f"leaf{i:03d}")==1,(name,i)
  else:assert result.stdout.count("deep-leaf")==1
  print(f"PASS: {name} tree complete under 64-FD limit")
