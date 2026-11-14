/* SPDX-License-Identifier: EUPL-1.2
 * What a Workbench default tool receives for a file name containing '#',
 * without eza or Limpet in between.
 *   wbprobe setup DIR LOGFILE   create DIR/"hash #1.txt" (no icon) and
 *                               DIR/"own #1.txt" with a project icon whose
 *                               default tool is this program, then record
 *                               the icon GetDiskObjectNew() gives each file
 *   wbprobe open NAME LOGFILE   OpenWorkbenchObjectA(NAME), as Limpet does
 *   (started from Workbench)    append every WBArg as parent:name to the log
 *                               named by the tool type LOG */
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/icon.h>
#include <proto/workbench.h>
#include <workbench/startup.h>
#include <workbench/icon.h>
#include <stdio.h>
#include <string.h>

static void line(CONST_STRPTR log, CONST_STRPTR text)
{
    BPTR f = Open(log, MODE_READWRITE);
    if (!f)
        return;
    Seek(f, 0, OFFSET_END);
    FPuts(f, text);
    FPuts(f, "\n");
    Close(f);
}

static void describe(CONST_STRPTR log, CONST_STRPTR name)
{
    struct DiskObject *icon = GetDiskObjectNew(name);
    char buf[600];
    STRPTR *tt;

    if (!icon) {
        line(log, "ICON none");
        return;
    }
    snprintf(buf, sizeof buf, "ICON %s type=%d tool=%s", name, (int)icon->do_Type,
              icon->do_DefaultTool ? (char *)icon->do_DefaultTool : "-");
    line(log, buf);
    for (tt = (STRPTR *)icon->do_ToolTypes; tt && *tt; tt++) {
        snprintf(buf, sizeof buf, "  TOOLTYPE %s", *tt);
        line(log, buf);
    }
    FreeDiskObject(icon);
}

int main(int argc, char **argv)
{
    char path[512], buf[700];

    if (argc == 0) {
        /* Started from Workbench: argv is the WBStartup message. */
        struct WBStartup *wb = (struct WBStartup *)argv;
        struct DiskObject *self;
        CONST_STRPTR log = NULL;
        LONG i;

        CurrentDir(wb->sm_ArgList[0].wa_Lock);
        self = GetDiskObject(wb->sm_ArgList[0].wa_Name);
        if (self)
            log = FindToolType(self->do_ToolTypes, "LOG");
        if (!log)
            log = "RAM:wbprobe-default.log";
        for (i = 0; i < wb->sm_NumArgs; i++) {
            char dir[300] = "?";
            NameFromLock(wb->sm_ArgList[i].wa_Lock, dir, sizeof dir);
            snprintf(buf, sizeof buf, "WBARG %d lock=%s name=[%s]", (int)i, dir, wb->sm_ArgList[i].wa_Name);
            line(log, buf);
        }
        if (self)
            FreeDiskObject(self);
        return 0;
    }
    if (argc == 4 && !strcmp(argv[1], "setup")) {
        struct DiskObject *icon;
        BPTR f;
        char tool[300];
        STRPTR types[2];

        snprintf(path, sizeof path, "%s/hash #1.txt", argv[2]);
        if ((f = Open(path, MODE_NEWFILE))) { FPuts(f, "hash file\n"); Close(f); }
        describe(argv[3], path);
        snprintf(path, sizeof path, "%s/own #1.txt", argv[2]);
        if ((f = Open(path, MODE_NEWFILE))) { FPuts(f, "own file\n"); Close(f); }
        icon = GetDefDiskObject(WBPROJECT);
        if (!icon) {
            line(argv[3], "SETUP no default project icon");
            return 20;
        }
        snprintf(tool, sizeof tool, "%s/wbprobe", argv[2]);
        icon->do_DefaultTool = tool;
        snprintf(buf, sizeof buf, "LOG=%s", argv[3]);
        types[0] = buf; types[1] = NULL;
        icon->do_ToolTypes = types;
        /* The default icon now points at local buffers: it is written, never
           freed, in this short-lived probe. */
        line(argv[3], PutDiskObject(path, icon) ? "SETUP own icon written" : "SETUP own icon failed");
        /* The tool needs its own icon carrying LOG, read back when started. */
        snprintf(path, sizeof path, "%s/wbprobe", argv[2]);
        icon->do_Type = WBTOOL;
        icon->do_DefaultTool = NULL;
        PutDiskObject(path, icon);
        snprintf(path, sizeof path, "%s/own #1.txt", argv[2]);
        describe(argv[3], path);
        return 0;
    }
    if (argc == 4 && !strcmp(argv[1], "open")) {
        BOOL ok = OpenWorkbenchObjectA(argv[2], NULL);
        snprintf(buf, sizeof buf, "OPEN [%s] returned %d", argv[2], (int)ok);
        line(argv[3], buf);
        return ok ? 0 : 5;
    }
    PutStr("wbprobe setup DIR LOG | open NAME LOG\n");
    return 20;
}
