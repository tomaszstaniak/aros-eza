import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("native_checker",Path(__file__).with_name("check_native.py"))
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
class NativeList(unittest.TestCase):
 def setUp(self):
  self.expected={'.hidden','alpha.txt','bad\\xff.bin','beta.txt','empty','file name.txt','sub','zażółć.txt'}
  self.header='Directory "RAM:test" on Wednesday 10/21/26:'
  self.rows=[f'{name}  3 ---rwed Today 01:06:56' for name in sorted(self.expected)]
  self.long='\n'.join(f'----rwed 3 ? 2026-10-21 01:06 {name}' for name in sorted(self.expected))
 def check(self,rows):checker.validate_native_list('\n'.join([self.header]+rows),self.long,self.expected)
 def test_complete(self):self.check(self.rows)
 def test_header_only(self):
  with self.assertRaises(AssertionError):self.check([])
 def test_missing(self):
  with self.assertRaises(AssertionError):self.check(self.rows[:-1])
 def test_duplicate(self):
  with self.assertRaises(AssertionError):self.check(self.rows+[self.rows[0]])
 def test_unrecognized(self):
  with self.assertRaises(AssertionError):self.check(self.rows+['broken data'])
 def test_unexpected(self):
  with self.assertRaises(AssertionError):self.check(self.rows+['extra  3 ---rwed Today 01:06:56'])
 def test_wrong_time(self):
  with self.assertRaises(AssertionError):self.check([row.replace('01:06','01:07') for row in self.rows])
if __name__=='__main__':unittest.main()
