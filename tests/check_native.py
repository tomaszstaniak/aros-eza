#!/usr/bin/env python3
# SPDX-License-Identifier: EUPL-1.2
import re,datetime,sys,json
from pathlib import Path
def validate_native_list(native, long, expected):
 header=re.search(r'on \w+ (\d+/\d+/\d+):',native)
 assert header, "Missing native List date header"
 date=datetime.datetime.strptime(header.group(1),'%m/%d/%y').strftime('%Y-%m-%d')
 seen=set()
 for row in native.splitlines():
  if not row.strip() or re.fullmatch(r'Directory \".*\" on \w+ \d+/\d+/\d+:',row) or re.fullmatch(r'\d+ files? - \d+ director(?:y|ies) - \d+ blocks used',row):continue
  match=re.fullmatch(r"(.*?)\s{2,}(\d+|Dir)\s+([hsparwed-]{7,8})\s+Today\s+(\d\d:\d\d):\d\d\s*",row)
  assert match, ("Unrecognized native List row",row)
  name,size,perms,clock=match.groups()
  assert name in expected and name not in seen,("Unexpected or duplicate native entry",name)
  seen.add(name)
  lines=[line for line in long.splitlines() if line.endswith(" "+name) or line.endswith(" '"+name+"'")]
  assert len(lines)==1,(name,lines)
  line=lines[0]
  assert date+' '+clock in line,(line,row)
  assert line.startswith(('-' if len(perms)==7 else '')+perms),(line,row)
  wanted='-' if size=='Dir' else size
  assert re.match(r'[hsparwed?-]{8}\s+'+re.escape(wanted)+r'\s+\?',line),(line,row)
 assert seen==expected,("Missing native List entries",expected-seen)

def main():
 dst=Path(sys.argv[1])
 generation=sys.argv[2] if len(sys.argv)>2 else ""
 def read(n):
  for prefix in ['efinal','erich','enil']:n=n.replace(prefix+'-',prefix+generation+'-')
  aliases=json.loads((dst/"keyboard-delivery.json").read_text()) if (dst/"keyboard-delivery.json").exists() else {}
  return (dst/aliases.get(n,n)).read_bytes().decode('utf-8',errors='backslashreplace')
 def names(n):return [s.strip("'")for s in read(n).splitlines()]
 expected={'.hidden','alpha.txt','bad\\xff.bin','beta.txt','empty','file name.txt','sub','zażółć.txt'}
 assert set(names('efinal-list.out'))==expected,names('efinal-list.out')
 assert set(names('efinal-assign.out'))==expected-{'.hidden'}
 assert names('efinal-assign.out')==names('efinal-relative.out')
 assert len(names('efinal-small.out'))==100 and set(names('efinal-small.out'))=={f'f{i:04d}.txt'for i in range(100)}
 assert len(names('efinal-large.out'))==2000 and set(names('efinal-large.out'))=={f'f{i:04d}.txt'for i in range(2000)}
 assert not read('efinal-empty.out').strip()
 for p in dst.glob('*.out'):assert b'\x1b' not in p.read_bytes(),p.name
 for p in dst.glob('*.err'):assert b'\x1b' not in p.read_bytes(),p.name
 assert names('efinal-pipe.out')==names('efinal-relative.out')
 for n in ['efinal-pipe-reader.rc','efinal-pipe-writer.rc','efinal-runner.rc','erich-runner.rc','efinal-unzip.rc','efinal-path.rc','efinal-narrow.rc','efinal-wide.rc']:assert read(n).strip()=='0',(n,read(n))
 assert read('efinal-ctrl.rc').strip()=='5'
 assert read('efinal-alive.txt').strip()=='ALIVE'
 assert 'Limpet' in read('efinal-con.err')
 for n in ['efinal-report.txt','erich-report.txt','enil-report.txt']:assert 'DONE errors=0' in read(n),(n,read(n))
 sort=names('efinal-sort.out');seq=['alpha.txt','bad\\xff.bin','beta.txt','file name.txt','zażółć.txt'];assert [sort.index(n)for n in seq]==sorted(sort.index(n)for n in seq),sort
 for n in expected|{'child'}:assert n in read('efinal-tree.out'),n
 long=read('efinal-long.out');assert '----r-e-' in long and '----rwed' in long
 for name,size in [('alpha.txt',3),('beta.txt',6),('file name.txt',9),('zażółć.txt',11),('bad\\xff.bin',4)]:
  line=next(l for l in long.splitlines()if name in l);assert re.match(r'[hsparwed?-]{8}\s+'+str(size)+r'\s+\?',line),line
 # Compare each file's date/minute and DOS protection with native List, same boot.
 validate_native_list(read('efinal-native-list.txt'),long,expected)
 print('PASS: exact sets (8/100/2000), sizes, dates/protection vs native List, sort/tree, assign/relative, plain files/pipe, CON refusal, help/version, Ctrl-C, narrow/wide RC and shell alive')
 for prefix in ['enil','erich']:
  for name in ['small','large']:
   m=re.search('CASE '+name+r' rc=0 expected=0 ticks=(\d+)',read(prefix+'-report.txt'));print(prefix,name,int(m.group(1))/50,'seconds')

 if generation == "2":
  assert read("edeny2-runner.rc").strip()=="0"
  assert "root=1 tree=1 recursive=1" in read("edeny2-report.txt")
  assert "native List rc=20" in read("edeny2-report.txt")
  print("PASS: native exclusive DOS lock propagates errors in root, recursive and tree views")

if __name__=="__main__":main()
