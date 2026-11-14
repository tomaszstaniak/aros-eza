/* SPDX-License-Identifier: EUPL-1.2 */
#include <proto/dos.h>
#include <dos/dos.h>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define ROOT "RAM:eza-dirprobe-997b9f64"
#define COUNT 160
static void mkdir_dos(const char *name){BPTR lock=CreateDir(name);if(lock)UnLock(lock);}
int main(int argc,char **argv){
 if(argc<2||argc>3){puts("dirprobe-c fixture|scan|hold|cleanup [result-tag]");return 20;}
 /* Result names never repeat: RESULTS: is FAT32 and must not be overwritten. */
 const char *tag=argc==3?argv[2]:"997b9f64";
 char path[256],logname[128];
 if(!strcmp(argv[1],"fixture")){
  BPTR old=Lock(ROOT,ACCESS_READ);if(old){UnLock(old);puts("fixture already exists; refusing reuse");return 20;}
  mkdir_dos(ROOT);
  for(int i=0;i<COUNT;i++){snprintf(path,sizeof path,ROOT "/d%03d",i);mkdir_dos(path);strcat(path,"/entry");BPTR out=Open(path,MODE_NEWFILE);if(!out)return 20;Write(out,"x",1);Close(out);}return 0;
 }
 if(!strcmp(argv[1],"cleanup")){
  for(int i=0;i<COUNT;i++){snprintf(path,sizeof path,ROOT "/d%03d/entry",i);DeleteFile(path);snprintf(path,sizeof path,ROOT "/d%03d",i);DeleteFile(path);}return DeleteFile(ROOT)?0:20;
 }
 int hold=!strcmp(argv[1],"hold");if(!hold&&strcmp(argv[1],"scan"))return 20;
 snprintf(logname,sizeof logname,"RESULTS:ecrash-c-%s-%s.txt",argv[1],tag);FILE *log=fopen(logname,"w");if(!log)return 20;
 DIR *retained[COUNT]={0};int failures=0;
 for(int i=0;i<COUNT;i++){
  snprintf(path,sizeof path,ROOT "/d%03d",i);fprintf(log,"BEFORE %d %s\n",i,path);fflush(log);
  errno=0;DIR *dir=opendir(path);if(!dir){fprintf(log,"OPEN_ERROR %d errno=%d\n",i,errno);fflush(log);failures++;break;}
  int entries=0;errno=0;while(readdir(dir))entries++;int read_error=errno;
  fprintf(log,"AFTER %d entries=%d errno=%d\n",i,entries,read_error);fflush(log);
  if(read_error)failures++;if(hold)retained[i]=dir;else if(closedir(dir))failures++;
 }
 for(int i=0;i<COUNT;i++)if(retained[i])closedir(retained[i]);
 fprintf(log,"DONE failures=%d\n",failures);fclose(log);return failures?5:0;
}
