/* SPDX-License-Identifier: EUPL-1.2
 * Native libgit2 discovery probe: for each path, what git_repository_discover
 * and git_repository_open_ext find, with the repository and work-directory
 * names libgit2 reports. Written for a repository whose .git sits at a
 * volume root (RAM:.git), which eza did not recognise.
 *   git_discover RESULTFILE PATH... */
#include <stdio.h>
#include <git2.h>

int main(int argc, char **argv)
{
    FILE *out;
    int i;

    if (argc < 3)
        return 20;
    out = fopen(argv[1], "w");
    if (!out)
        return 20;
    git_libgit2_init();
    for (i = 2; i < argc; i++) {
        git_buf found = {0};
        git_repository *repo = NULL;
        const git_error *e;
        int rc = git_repository_discover(&found, argv[i], 0, NULL);

        e = git_error_last();
        fprintf(out, "DISCOVER %s rc=%d found=%s err=%s\n", argv[i], rc,
                rc == 0 ? found.ptr : "-", rc && e ? e->message : "-");
        git_buf_dispose(&found);
        rc = git_repository_open_ext(&repo, argv[i], 0, NULL);
        e = git_error_last();
        fprintf(out, "OPEN_EXT %s rc=%d path=%s workdir=%s err=%s\n", argv[i], rc,
                repo ? git_repository_path(repo) : "-",
                repo && git_repository_workdir(repo) ? git_repository_workdir(repo) : "-",
                rc && e ? e->message : "-");
        if (repo) {
            int ignored = -1;
            unsigned int status = 0;
            int s = git_status_file(&status, repo, "modified.txt");
            git_ignore_path_is_ignored(&ignored, repo, "ignored.txt");
            fprintf(out, "STATUS modified.txt rc=%d status=%u ignored.txt ignored=%d\n",
                    s, status, ignored);
            {
                git_status_options o = GIT_STATUS_OPTIONS_INIT;
                git_status_list *list = NULL;
                size_t k;
                o.flags = GIT_STATUS_OPT_INCLUDE_UNTRACKED | GIT_STATUS_OPT_INCLUDE_IGNORED;
                if (git_status_list_new(&list, repo, &o) == 0) {
                    for (k = 0; k < git_status_list_entrycount(list) && k < 40; k++) {
                        const git_status_entry *en = git_status_byindex(list, k);
                        const char *p = en->index_to_workdir ? en->index_to_workdir->new_file.path
                                                             : en->head_to_index->new_file.path;
                        fprintf(out, "  ENTRY %s %u\n", p, en->status);
                    }
                    git_status_list_free(list);
                }
            }
            git_repository_free(repo);
        }
        fflush(out);
    }
    git_libgit2_shutdown();
    fclose(out);
    return 0;
}
