/* Native local-repository API proof; report always goes to the named file. */
#include <stdio.h>
#include <string.h>
#include <git2.h>
static FILE *report;
static int errors;
static void check(int ok, const char *what) { fprintf(report, "%s %s\n", ok?"PASS":"FAIL", what); if(!ok)errors++; }
int main(int argc,char **argv) {
 git_repository *repo=NULL;git_reference *head=NULL;git_status_list *list=NULL;
 git_status_options options=GIT_STATUS_OPTIONS_INIT;unsigned seen=0;size_t i;
 if(argc!=3)return 20;
 report=fopen(argv[2],"w");if(!report)return 20;
 check(git_libgit2_init()>0,"init");
 if(git_repository_open(&repo,argv[1])<0) {
  const git_error *error=git_error_last();fprintf(report,"ERROR open %s: %s\n",argv[1],error?error->message:"unknown");errors++;goto done;
 }
 check(git_repository_head(&head,repo)==0,"head");
 if(head)check(strcmp(git_reference_shorthand(head),"main")==0,"branch main");
 options.flags=GIT_STATUS_OPT_INCLUDE_UNTRACKED|GIT_STATUS_OPT_INCLUDE_IGNORED|GIT_STATUS_OPT_RECURSE_UNTRACKED_DIRS;
 check(git_status_list_new(&list,repo,&options)==0,"status list");
 if(list)for(i=0;i<git_status_list_entrycount(list);i++) {
  const git_status_entry *entry=git_status_byindex(list,i);
  const char *name=entry->index_to_workdir?entry->index_to_workdir->new_file.path:entry->head_to_index->new_file.path;
  unsigned bit=0,wanted=0;
  if(!strcmp(name,"modified.txt")){bit=1;wanted=GIT_STATUS_WT_MODIFIED;}
  else if(!strcmp(name,"deleted.txt")){bit=2;wanted=GIT_STATUS_WT_DELETED;}
  else if(!strcmp(name,"staged.txt")){bit=4;wanted=GIT_STATUS_INDEX_NEW;}
  else if(!strcmp(name,"untracked.txt")){bit=8;wanted=GIT_STATUS_WT_NEW;}
  else if(!strcmp(name,"ignored.txt")){bit=16;wanted=GIT_STATUS_IGNORED;}
  fprintf(report,"ENTRY %s status=%u expected=%u\n",name,entry->status,wanted);
  check(bit && !(seen&bit) && entry->status==wanted,"exact status");seen|=bit;
 }
 check(seen==31,"all five expected status entries, clean file absent");
 done:
 git_status_list_free(list);git_reference_free(head);git_repository_free(repo);git_libgit2_shutdown();
 fprintf(report,"DONE errors=%d\n",errors);fclose(report);return errors?20:0;
}
