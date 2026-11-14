/* SPDX-License-Identifier: EUPL-1.2
 * The steps of C:Pipe (workbench/c/shellcommands/Pipe.c), one by one, to see
 * which fails when a Shell `|` pipeline produces nothing on AROS One. */
#include <proto/exec.h>
#include <proto/dos.h>
#include <dos/dostags.h>
#include <stdio.h>
int main(void)
{
    TEXT name[64] = "";
    BPTR w, r = BNULL, in, lock;
    LONG rc = -1;
    w = Open((CONST_STRPTR)"PIPE:*", MODE_NEWFILE);
    printf("Open(PIPE:*) %s ioerr=%ld\n", w ? "ok" : "FAIL", (long)IoErr());
    if (w) {
        LONG n = NameFromFH(w, name, sizeof name);
        printf("NameFromFH %s name=[%s] ioerr=%ld\n", n ? "ok" : "FAIL", name, (long)IoErr());
        if (n) {
            r = Open(name, MODE_OLDFILE);
            printf("Open(%s, OLDFILE) %s ioerr=%ld\n", name, r ? "ok" : "FAIL", (long)IoErr());
        }
    }
    lock = DupLockFromFH(Input());
    printf("DupLockFromFH(Input()) %s ioerr=%ld\n", lock ? "ok" : "FAIL (NULL)", (long)IoErr());
    in = lock ? OpenFromLock(lock) : BNULL;
    printf("OpenFromLock %s ioerr=%ld\n", in ? "ok" : "FAIL", (long)IoErr());
    if (w && r) {
        rc = SystemTags((CONST_STRPTR)"Echo pipe-data", SYS_Input, in, SYS_Output, w, SYS_Asynch, TRUE, TAG_DONE);
        printf("SystemTags(async Echo) rc=%ld ioerr=%ld\n", (long)rc, (long)IoErr());
        if (rc != -1) {
            char buf[64] = "";
            LONG got = Read(r, buf, sizeof buf - 1);
            if (got > 0) buf[got] = 0;
            printf("Read from pipe got=%ld [%s]\n", (long)got, got > 0 ? buf : "");
        }
        Close(r);
    }
    if (in && rc == -1) Close(in);
    return 0;
}
