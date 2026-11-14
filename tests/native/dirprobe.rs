// SPDX-License-Identifier: EUPL-1.2
use std::{fs::{self,DirEntry,File},io::{self,Write}};
const ROOT:&str="RAM:eza-dirprobe-997b9f64";
fn run()->io::Result<()> {
 let mode=std::env::args().nth(1).unwrap_or_default();
 // Result names never repeat: RESULTS: is FAT32 and must not be overwritten.
 let tag=std::env::args().nth(2).unwrap_or_else(||"997b9f64".into());
 if mode!="scan"&&mode!="hold"{return Err(io::Error::other("dirprobe-rust scan|hold [result-tag]"));}
 let mut log=File::create(format!("RESULTS:ecrash-rust-{mode}-{tag}.txt"))?;
 let mut retained:Vec<Vec<DirEntry>>=Vec::new();
 for i in 0..160 {
  let path=format!("{ROOT}/d{i:03}");writeln!(log,"BEFORE {i} {path}")?;log.flush()?;
  let entries=match fs::read_dir(&path).and_then(|iter|iter.collect::<io::Result<Vec<_>>>()) {
   Ok(entries)=>entries,
   Err(error)=>{writeln!(log,"OPEN_OR_READ_ERROR {i} kind={:?} errno={:?} {error}",error.kind(),error.raw_os_error())?;log.flush()?;return Err(error);}
  };
  writeln!(log,"AFTER {i} entries={}",entries.len())?;log.flush()?;
  if mode=="hold"{retained.push(entries);}
 }
 drop(retained);writeln!(log,"DONE failures=0")?;log.flush()
}
fn main(){if let Err(error)=run(){eprintln!("dirprobe-rust: {error}");std::process::exit(5);}}
