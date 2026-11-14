import hashlib, importlib.util, io, tarfile, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("git_deps",Path(__file__).resolve().parents[1]/"scripts/git_deps.py")
deps=importlib.util.module_from_spec(spec);spec.loader.exec_module(deps)
def snapshot(root):return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}
class GitInputs(unittest.TestCase):
 def test_checksum_and_reconstruction_are_both_enforced(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cache=root/"dependency-archives";cache.mkdir()
   archive=cache/(deps.NAME+".crate")
   with tarfile.open(archive,"w") as out:
    data=b"before\n";entry=tarfile.TarInfo(deps.NAME+"/source.c");entry.size=len(data);out.addfile(entry,io.BytesIO(data))
   checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
   patches=root/"patches/deps";patches.mkdir(parents=True)
   (patches/"libgit2-sys-0.18.5-aros.patch").write_text("--- a/source.c\n+++ b/source.c\n@@ -1 +1 @@\n-before\n+after\n")
   with patch.object(deps,"CHECKSUM",checksum),patch.object(deps,"ROOT",root):
    dest,_=deps.stage(root,root/"deps",snapshot)
    self.assertEqual((dest/"source.c").read_text(),"after\n")
    deps.stage(root,root/"deps",snapshot)
    (dest/"source.c").write_text("tampered\n")
    with self.assertRaisesRegex(RuntimeError,"reconstruction"):deps.stage(root,root/"deps",snapshot)
    self.assertEqual((dest/"source.c").read_text(),"tampered\n")
    archive.write_bytes(b"bad archive")
    with self.assertRaisesRegex(RuntimeError,"checksum"):deps.stage(root,root/"deps",snapshot)
if __name__=="__main__":unittest.main()
