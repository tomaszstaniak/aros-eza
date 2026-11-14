import importlib.util,io,tarfile,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location("eza_port",Path(__file__).resolve().parents[1]/"scripts/eza.py")
port=importlib.util.module_from_spec(spec);spec.loader.exec_module(port)
class Inputs(unittest.TestCase):
 def archive(self):
  b=io.BytesIO()
  with tarfile.open(fileobj=b,mode="w") as t:
   data=b"pinned SDK";i=tarfile.TarInfo("sdk/format.c");i.size=len(data);i.mode=0o644;t.addfile(i,io.BytesIO(data))
  return b.getvalue()
 def test_stale_sdk_is_rejected_without_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   dest=Path(d)/"pin";archive=self.archive();port.stage_pin(dest,archive);p=dest/"sdk/format.c";p.write_bytes(b"local change")
   with self.assertRaises(RuntimeError):port.stage_pin(dest,archive)
   self.assertEqual(p.read_bytes(),b"local change")
 def test_extra_sdk_file_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   dest=Path(d)/"pin";archive=self.archive();port.stage_pin(dest,archive);(dest/"extra").write_text("local")
   with self.assertRaises(RuntimeError):port.stage_pin(dest,archive)
class GeneratedInputs(unittest.TestCase):
 def test_cached_libc_is_reconstructed_and_tampering_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);libc=root/"libc"
   def generate(args):
    dest=Path(args[3]);dest.mkdir();(dest/"lib.rs").write_text("pinned")
   with patch.object(port,"run",side_effect=generate) as run:
    port.stage_libc(root,libc,root)
    port.stage_libc(root,libc,root)
    self.assertEqual(run.call_count,2)
    (libc/"lib.rs").write_text("tampered")
    with self.assertRaises(RuntimeError):port.stage_libc(root,libc,root)
    self.assertEqual((libc/"lib.rs").read_text(),"tampered")
 def test_std_identity_tracks_actual_sysroot_source(self):
  with tempfile.TemporaryDirectory() as d:
   library=Path(d)/"lib/rustlib/src/rust/library";(library/"std/src").mkdir(parents=True)
   source=library/"std/src/lib.rs";source.write_text("before")
   with patch.object(port.subprocess,"check_output",return_value=d+"\n"):
    before=port.std_identity("test");source.write_text("after")
    self.assertNotEqual(before,port.std_identity("test"))
if __name__=="__main__":unittest.main()
