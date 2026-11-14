/* SPDX-License-Identifier: EUPL-1.2
 * Native acceptance runner for the packaged eza (candidate 3 onward).
 *   acceptance plain   run from an ordinary CON: Shell (files, pipes, CON refusal)
 *   acceptance rich    run from the Limpet window under test (terminal cases, timings)
 *   acceptance stdin <file>  copy Input() to <file> (reader end of a Shell pipe)
 *   acceptance clean   delete exactly the fixtures created by plain
 * Every case result goes to RESULTS:ez3-<case>-<TAG>.{out,err} and one line in
 * the report; the console under test is never parsed. Fixtures live only on
 * RAM: under a session-specific name and are refused if they already exist. */
#include <proto/dos.h>
#include <proto/exec.h>
#include <dos/dostags.h>
#include <dos/dos.h>
#include <dos/dosextens.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TAG "b2d5e8"
#define Q "RAM:ez3-qa-" TAG
#define EZA "RAM:demo/Eza/eza"
#define ASSIGN "EZA3" TAG

static FILE *report;
static int errors;

static void directory(const char *path){BPTR p=CreateDir((CONST_STRPTR)path);if(p)UnLock(p);else fprintf(report,"MKDIR_FAIL %s %ld\n",path,(long)IoErr());}
static void file(const char *path,int size){BPTR p=Open((CONST_STRPTR)path,MODE_NEWFILE);if(!p){fprintf(report,"CREATE_FAIL %s %ld\n",path,(long)IoErr());errors++;return;}for(int i=0;i<size;i++)Write(p,"x",1);Close(p);}
static long ticks(struct DateStamp d){return (long)d.ds_Days*24*60*60*50+(long)d.ds_Minute*60*50+d.ds_Tick;}
static int exists(const char *path){BPTR l=Lock((CONST_STRPTR)path,ACCESS_READ);if(l){UnLock(l);return 1;}return 0;}

/* out: 0 = RESULTS file, 1 = this process's console, 2 = NIL: (timing only). */
static long run(const char *name,const char *args,int out,long expected){
 char cmd[1200],path[256];struct DateStamp a,b;BPTR o,e;
 snprintf(cmd,sizeof cmd,EZA " %s",args);
 snprintf(path,sizeof path,"RESULTS:ez3-%s-" TAG ".out",name);
 o=out==1?Output():Open((CONST_STRPTR)(out==2?"NIL:":path),MODE_NEWFILE);
 snprintf(path,sizeof path,"RESULTS:ez3-%s-" TAG ".err",name);
 e=out==2?Open((CONST_STRPTR)"NIL:",MODE_NEWFILE):Open((CONST_STRPTR)path,MODE_NEWFILE);
 if(!o||!e){fprintf(report,"OPEN_FAIL %s\n",name);errors++;return -1;}
 DateStamp(&a);
 LONG rc=SystemTags((CONST_STRPTR)cmd,SYS_Input,Input(),SYS_Output,o,SYS_Error,e,NP_StackSize,1024*1024,TAG_END);
 DateStamp(&b);
 if(out!=1)Close(o);Close(e);
 fprintf(report,"CASE %s rc=%ld expected=%ld ticks=%ld\n",name,(long)rc,expected,ticks(b)-ticks(a));fflush(report);
 if(expected>=0&&rc!=expected)errors++;
 return ticks(b)-ticks(a);
}

/* Same traversal eza performs before formatting: enumerate, then stat each
 * entry, through the same posixc calls Rust std uses. No output. */
static long read_only(const char *dir,int *count){
 struct DateStamp a,b;char path[512];struct stat st;struct dirent *d;DIR *h;*count=0;
 DateStamp(&a);h=opendir(dir);
 if(h){while((d=readdir(h))){snprintf(path,sizeof path,"%s/%s",dir,d->d_name);if(!stat(path,&st))(*count)++;}closedir(h);}
 DateStamp(&b);return ticks(b)-ticks(a);
}

static void fixtures(void){
 char path[512];
 directory(Q);directory(Q "/tiny");directory(Q "/tiny/sub");directory(Q "/tiny/empty");
 file(Q "/tiny/alpha.txt",12);file(Q "/tiny/beta.txt",6);file(Q "/tiny/file name.txt",9);file(Q "/tiny/zażółć.txt",3);file(Q "/tiny/bad\xff.bin",4);file(Q "/tiny/.hidden",5);file(Q "/tiny/sub/child",7);
 SetProtection((CONST_STRPTR)Q "/tiny/alpha.txt",FIBF_WRITE|FIBF_DELETE);SetProtection((CONST_STRPTR)Q "/tiny/beta.txt",0);
 directory(Q "/small");directory(Q "/large");
 for(int i=0;i<2000;i++){snprintf(path,sizeof path,Q "/large/f%04d.txt",i);file(path,1);if(i<100){snprintf(path,sizeof path,Q "/small/f%04d.txt",i);file(path,1);}}
 /* 72 nested directories: deeper than a 64-descriptor table, still well
  * under the ~255-character absolute path limit seen on AROS One. */
 strcpy(path,Q "/deep");directory(path);
 for(int i=0;i<72;i++){strcat(path,"/d");directory(path);}
 strcat(path,"/deep-leaf");file(path,1);
 directory(Q "/denied");directory(Q "/denied/locked");
 directory(Q "/noread");file(Q "/noread/inside",1);
 directory(Q "/bad\xff" "dir");directory(Q "/bad\xff" "dir/sub");
 directory(Q "/link");file(Q "/link/space name.txt",10);file(Q "/link/100% #1 żółć.txt",10);
}

static void plain(void){
 char cmd[512];
 if(exists(Q)){fprintf(report,"REFUSED existing fixture\n");errors++;return;}
 {struct DosList *l=LockDosList(LDF_ASSIGNS|LDF_READ);int a=FindDosEntry(l,(CONST_STRPTR)ASSIGN,LDF_ASSIGNS)!=0;UnLockDosList(LDF_ASSIGNS|LDF_READ);if(a){fprintf(report,"REFUSED existing assignment\n");errors++;return;}}
 fixtures();
 /* Why std::fs::canonicalize and libgit2 failed on candidate 3: record what
  * crt.library realpath() and getcwd() return for AmigaDOS paths. */
 {const char *paths[]={Q "/tiny",Q "/tiny/alpha.txt","RAM:","SYS:C",NULL};char out[1024];
  for(int i=0;paths[i];i++){errno=0;char *r=realpath(paths[i],out);fprintf(report,"REALPATH %s -> %s errno=%d\n",paths[i],r?r:"(null)",errno);}
  errno=0;fprintf(report,"GETCWD %s errno=%d\n",getcwd(out,sizeof out)?out:"(null)",errno);fflush(report);}
 run("version","--version",0,0);run("help","--help",0,0);
 /* The exact command that crashed candidate 2, here into a file. */
 run("crash-file","-Tl -L2 RAM:demo/Eza/LICENSES",0,0);
 run("list","-1a --color=always --no-quotes " Q "/tiny",0,0);
 run("long","-la --time-style=long-iso " Q "/tiny",0,0);
 run("sort","-1 --sort=size --no-quotes " Q "/tiny",0,0);
 run("tree","-Ta -L2 --no-quotes " Q "/tiny",0,0);
 run("small","-1 " Q "/small",0,0);run("large","-1 " Q "/large",0,0);
 run("wide","-Tl --no-quotes RAM:eza-dirprobe-997b9f64",0,0);
 run("wide-l2","-Tl -L2 --no-quotes RAM:eza-dirprobe-997b9f64",0,0);
 run("deep","-T --no-quotes " Q "/deep",0,0);
 run("roots","-d RAM: SYS:",0,0);
 run("volname","-1 --no-quotes \"Ram Disk:ez3-qa-" TAG "/tiny\"",0,0);
 run("empty","-1 " Q "/tiny/empty",0,0);
 run("missing",Q "/does-not-exist",0,2);
 run("con",Q "/tiny",1,5);
 run("con-icons","--icons=always " Q "/tiny",1,5);
 run("file-icons","-1 --icons=always --no-quotes " Q "/tiny",0,0);
 run("file-links","-1 --hyperlink=always --no-quotes " Q "/link",0,0);
 run("parent-ref","-1d --no-quotes " Q "/tiny/sub//",0,0);
 run("parent-bad","-1d --no-quotes " Q "/bad\xff" "dir/sub//",0,0);
 {BPTR old=CurrentDir(Lock((CONST_STRPTR)Q,ACCESS_READ));run("relative","-1 --no-quotes tiny",0,0);BPTR here=CurrentDir(old);if(here)UnLock(here);}
 {BPTR old=CurrentDir(Lock((CONST_STRPTR)Q "/tiny/sub",ACCESS_READ));run("slash","-1 --no-quotes /",0,0);BPTR here=CurrentDir(old);if(here)UnLock(here);}
 /* No operand and "." mean the current drawer (no "." entry in AmigaDOS). */
 {BPTR old=CurrentDir(Lock((CONST_STRPTR)Q "/tiny",ACCESS_READ));
  run("cwd-default","-1 --no-quotes",0,0);run("cwd-dot","-1 --no-quotes .",0,0);
  run("cwd-long","-l --no-quotes",0,0);run("cwd-tree","-T --no-quotes",0,0);
  BPTR here=CurrentDir(old);if(here)UnLock(here);}
 /* POSIX "." and ".." operands, translated only when the literal name is missing. */
 {BPTR old=CurrentDir(Lock((CONST_STRPTR)Q "/tiny/sub",ACCESS_READ));
  run("posix-dots","-1 --no-quotes ../alpha.txt ./child",0,0);
  run("posix-missing","-1 --no-quotes ./nope",0,2);
  BPTR here=CurrentDir(old);if(here)UnLock(here);}
 {BPTR old=CurrentDir(Lock((CONST_STRPTR)"RAM:ez3git-" TAG "/git-fixture",ACCESS_READ));
  run("cwd-git","-la --git --no-time --no-user --no-permissions --no-quotes",0,0);
  BPTR here=CurrentDir(old);if(here)UnLock(here);}
 {BPTR t=Lock((CONST_STRPTR)Q "/tiny",ACCESS_READ);if(t&&AssignLock((CONST_STRPTR)ASSIGN,t))run("assign","-1 --no-quotes " ASSIGN ":",0,0);else{if(t)UnLock(t);errors++;}AssignLock((CONST_STRPTR)ASSIGN,0);}
 /* Several operands: a failing operand must not hide later ones, and a later
  * failure must not lower an earlier, higher status. */
 run("multi-missing","-1 --no-quotes " Q "/tiny " Q "/missing " Q "/small",0,2);
 {BPTR lock=Lock((CONST_STRPTR)Q "/denied/locked",EXCLUSIVE_LOCK);
  if(!lock){fprintf(report,"LOCK_FAIL %ld\n",(long)IoErr());errors++;}
  else{
   run("lock-root","-1 " Q "/denied/locked " Q "/small",0,1);
   run("lock-tree","-T --no-quotes " Q "/denied " Q "/tiny",0,1);
   run("lock-recursive","-R --no-quotes " Q "/denied " Q "/tiny",0,1);
   run("lock-then-missing","-T " Q "/denied " Q "/missing",0,2);
   run("missing-then-lock","-T " Q "/missing " Q "/denied",0,2);
   snprintf(cmd,sizeof cmd,"List " Q "/denied/locked >RESULTS:ez3-lock-native-" TAG ".out");
   fprintf(report,"NATIVE_LIST_LOCKED rc=%ld\n",(long)SystemTags((CONST_STRPTR)cmd,TAG_END));
   UnLock(lock);
  }}
 /* Read protection on a drawer: recorded, not assumed (handlers differ). */
 SetProtection((CONST_STRPTR)Q "/noread",FIBF_READ);
 run("noread","-1 " Q "/noread " Q "/small",0,-1);
 snprintf(cmd,sizeof cmd,"List " Q "/noread >RESULTS:ez3-noread-native-" TAG ".out");
 fprintf(report,"NATIVE_LIST_NOREAD rc=%ld\n",(long)SystemTags((CONST_STRPTR)cmd,TAG_END));
 SetProtection((CONST_STRPTR)Q "/noread",0);
 /* Git, local repositories only. */
 run("git-long","-la --git --no-time --no-user --no-permissions --no-quotes RAM:ez3git-" TAG "/git-fixture",0,0);
 run("git-repos","-l --git-repos --no-time --no-user --no-permissions --no-quotes RAM:ez3git-" TAG,0,0);
 /* A repository at a volume root (unpacked into RAM: by the script). */
 run("git-root","-l --git --no-time --no-user --no-permissions --no-quotes RAM:modified.txt RAM:staged.txt RAM:clean.txt",0,0);
 run("git-root-ignore","-1 --git-ignore --no-quotes RAM:",0,0);
 run("git-ignore","-T --git --git-ignore --no-quotes RAM:ez3git-" TAG "/git-fixture",0,0);
 snprintf(cmd,sizeof cmd,"List " Q "/tiny >RESULTS:ez3-native-list-" TAG ".txt");SystemTags((CONST_STRPTR)cmd,TAG_END);
}

static void rich(void){
 char path[512];int n;long t;
 run("r-crash","-Tl -L2 RAM:demo/Eza/LICENSES",1,0);
 run("r-grid","-G " Q "/tiny",1,0);
 run("r-long","-la " Q "/tiny",1,0);
 run("r-wide","-T -L2 RAM:eza-dirprobe-997b9f64",1,0);
 run("r-deep","-T " Q "/deep",1,0);
 run("r-git","-l --git " "RAM:ez3git-" TAG "/git-fixture",1,0);
 run("r-icons-1","-1 --icons=always " Q "/tiny",1,0);
 run("r-icons-grid","-G --icons=always " Q "/large",1,0);
 run("r-icons-long","-l --icons=always " Q "/tiny",1,0);
 run("r-links","-1 --hyperlink=always " Q "/link",1,0);
 run("r-links-long","-l --icons=always --hyperlink=always " Q "/link " Q "/tiny",1,0);
 /* Same boot, three repetitions each. read: enumerate+stat only; nil: eza
  * with output to NIL: (start-up + read + format); term: eza into this
  * console; type: C:Type of eza's own plain output file into this console
  * (terminal output of the same text without eza). */
 for(int rep=0;rep<3;rep++){
  const char *dirs[2]={Q "/small",Q "/large"},*names[2]={"small","large"};
  snprintf(path,sizeof path,"t%d-start",rep);run(path,"--version",2,0);
  for(int i=0;i<2;i++){
   t=read_only(dirs[i],&n);fprintf(report,"TIME read %s rep=%d entries=%d ticks=%ld\n",names[i],rep,n,t);
   char args[256];
   snprintf(path,sizeof path,"t%d-nil1-%s",rep,names[i]);snprintf(args,sizeof args,"-1 %s",dirs[i]);run(path,args,2,0);
   snprintf(path,sizeof path,"t%d-nill-%s",rep,names[i]);snprintf(args,sizeof args,"-l %s",dirs[i]);run(path,args,2,0);
   snprintf(path,sizeof path,"t%d-file-%s",rep,names[i]);run(path,args,0,0);
   snprintf(path,sizeof path,"t%d-term1-%s",rep,names[i]);snprintf(args,sizeof args,"-1 %s",dirs[i]);run(path,args,1,0);
   snprintf(path,sizeof path,"t%d-terml-%s",rep,names[i]);snprintf(args,sizeof args,"-l %s",dirs[i]);run(path,args,1,0);
   {struct DateStamp a,b;char cmd[256];snprintf(cmd,sizeof cmd,"C:Type RESULTS:ez3-t%d-file-%s-" TAG ".out",rep,names[i]);
    DateStamp(&a);LONG rc=SystemTags((CONST_STRPTR)cmd,SYS_Input,Input(),SYS_Output,Output(),TAG_END);DateStamp(&b);
    fprintf(report,"TIME type-l %s rep=%d rc=%ld ticks=%ld\n",names[i],rep,(long)rc,ticks(b)-ticks(a));fflush(report);}
  }
 }
}

static void clean(void){
 char path[512];int depth;
 for(int i=0;i<2000;i++){snprintf(path,sizeof path,Q "/large/f%04d.txt",i);DeleteFile((CONST_STRPTR)path);if(i<100){snprintf(path,sizeof path,Q "/small/f%04d.txt",i);DeleteFile((CONST_STRPTR)path);}}
 const char *names[]={Q "/tiny/alpha.txt",Q "/tiny/beta.txt",Q "/tiny/file name.txt",Q "/tiny/zażółć.txt",Q "/tiny/bad\xff.bin",Q "/tiny/.hidden",Q "/tiny/sub/child",Q "/tiny/sub",Q "/tiny/empty",Q "/tiny",Q "/small",Q "/large",Q "/denied/locked",Q "/denied",Q "/noread/inside",Q "/noread",Q "/bad\xff" "dir/sub",Q "/bad\xff" "dir",Q "/link/space name.txt",Q "/link/100% #1 żółć.txt",Q "/link",NULL};
 for(int i=0;names[i];i++){SetProtection((CONST_STRPTR)names[i],0);if(!DeleteFile((CONST_STRPTR)names[i])){fprintf(report,"DELETE_FAIL %s %ld\n",names[i],(long)IoErr());errors++;}}
 /* Innermost first, by depth, never by pattern. */
 for(depth=73;depth>=0;depth--){
  strcpy(path,Q "/deep");for(int i=0;i<depth;i++)strcat(path,"/d");
  if(depth==73){strcpy(path,Q "/deep");for(int i=0;i<72;i++)strcat(path,"/d");strcat(path,"/deep-leaf");}
  if(!DeleteFile((CONST_STRPTR)path)){fprintf(report,"DELETE_FAIL depth=%d %ld\n",depth,(long)IoErr());errors++;}
 }
 if(!DeleteFile((CONST_STRPTR)Q)){fprintf(report,"DELETE_FAIL root %ld\n",(long)IoErr());errors++;}
}

int main(int argc,char **argv){
 char path[256];
 if(argc==3&&!strcmp(argv[1],"stdin")){
  BPTR out=Open((CONST_STRPTR)argv[2],MODE_NEWFILE);char buf[512];LONG n;if(!out)return 20;
  while((n=Read(Input(),buf,sizeof buf))>0)Write(out,buf,n);Close(out);return n<0?20:0;
 }
 if(argc!=2){puts("acceptance plain|rich|clean|stdin <file>");return 20;}
 snprintf(path,sizeof path,"RESULTS:ez3-%s-report-" TAG ".txt",argv[1]);
 report=fopen(path,"w");if(!report)return 20;
 if(!strcmp(argv[1],"plain"))plain();else if(!strcmp(argv[1],"rich"))rich();else if(!strcmp(argv[1],"clean"))clean();else{fclose(report);return 20;}
 fprintf(report,"DONE errors=%d\n",errors);fclose(report);return errors?20:0;
}
