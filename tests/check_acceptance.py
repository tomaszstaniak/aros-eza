#!/usr/bin/env python3
# SPDX-License-Identifier: EUPL-1.2
"""Check collected results of tests/native/acceptance.c and the c7 scripts.

Usage: check_acceptance.py RESULTS-DIR TAG HOLD-RESULTS-DIR HOLD-TAG

The Rust hold probe crashes crt.library on purpose, so it runs in a boot of
its own, with its own tag.

Asserts file contents, not only return codes. Prints the same-boot timing
summary (DateStamp ticks, 50 per second) at the end."""
import re, statistics, sys
from pathlib import Path
from check_native import validate_native_list

def main():
    dst, tag = Path(sys.argv[1]), sys.argv[2]
    hold = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    hold_tag = sys.argv[4] if len(sys.argv) > 4 else tag
    def raw(name):
        stem, ext = name.rsplit(".", 1)
        return (dst / f"ez3-{stem}-{tag}.{ext}").read_bytes()
    def read(name): return raw(name).decode("utf-8", errors="backslashreplace")
    def lines(name): return [l.strip("'") for l in read(name).splitlines()]
    def rc(name): return read(name + ".rc").strip()
    failures = []
    def check(ok, what):
        if not ok: failures.append(what)

    tiny = {"alpha.txt", "bad\\xff.bin", "beta.txt", "empty", "file name.txt", "sub", "zażółć.txt"}
    plain = read("plain-report.txt")
    check("DONE errors=0" in plain, "plain runner errors")
    check("DONE errors=0" in read("rich-report.txt"), "rich runner errors")
    for name, want in {"unzip": "0", "unzipgit": "0", "plain": "0", "rich": "0", "direct-crash": "0",
                       "dpfix": "0", "dpcscan": "0", "dprscan": "0", "pipe-reader": "0", "pipe-writer": "0",
                       "gitprobe": "0", "linkprobe": "0", "iconprobe": "0", "ctrl": "5",
                       "s40-crash": "0", "s40-wide": "0", "s40-deep": "0", "s40-git": "0",
                       "s40-gitignore": "0", "s40-links": "0", "s40-help": "0", "s40-version": "0",
                       "s40-badopt": "2", "s40-missing": "2", "s40-panic": "101", "unzipgitroot": "0"}.items():
        check(rc(name) == want, f"{name}.rc is {rc(name)!r}, expected {want}")
    check(read("stack.txt").strip() == "Current stack size is 40960 bytes", "default Shell stack not 40960")
    check(read("s40-done.txt").strip() == "S40-DONE", "default-stack block did not finish")
    # The next command after Ctrl-C ran. (An appended "ALIVE" line was lost on
    # the FAT32 results disk in one run; the screenshot shows the Shell.)
    if (dst / f"ez3-alive-{tag}.txt").exists():
        check("v0.23.5 [+git]" in read("alive.txt"), "command after Ctrl-C did not run")
    else:
        print("NOTE: no alive file; the Shell after Ctrl-C is checked on the screenshot")
    check(read("plain-done.txt").strip() == "PLAIN-DONE", "plain script did not finish")

    # Plain output: no escape sequence anywhere, colour and links forced or not.
    for p in dst.glob(f"ez3-*-{tag}.out"):
        if p.name.startswith(("ez3-t0-", "ez3-t1-", "ez3-t2-")) or "native" in p.name:
            continue
        check(b"\x1b" not in p.read_bytes(), f"escape sequence in {p.name}")
        check(not re.search(rb"\xef[\x80-\xbf][\x80-\xbf]|\xf3[\x80-\xbf]{3}", p.read_bytes()) or p.name.startswith("ez3-s40-help"),
              f"private-use icon glyph in plain {p.name}")

    check(set(lines("list.out")) == tiny | {".hidden"}, "list entries")
    ordered = ["alpha.txt", "bad\\xff.bin", "beta.txt", "empty", "file name.txt", "sub", "zażółć.txt"]
    for name in ["relative", "slash", "assign", "volname", "file-icons", "cwd-default", "cwd-dot"]:
        check(lines(name + ".out") == ordered, f"{name} entries or order")
    check(lines("pipe.out") == lines("relative.out"), "PIPE: output differs from file output")
    check(set(lines("file-links.out")) == {"100% #1 żółć.txt", "space name.txt"}, "file-links entries")
    check(lines("small.out") == [f"f{i:04d}.txt" for i in range(100)], "small: exact 100 entries")
    check(lines("large.out") == [f"f{i:04d}.txt" for i in range(2000)], "large: exact 2000 entries")
    check(not read("empty.out").strip(), "empty drawer listed entries")
    check(lines("roots.out") == ["RAM:", "SYS:"], "roots")
    sort = lines("sort.out")
    # Sizes 3, 4, 6, 9, 12 deliberately disagree with name order.
    files = ["zażółć.txt", "bad\\xff.bin", "beta.txt", "file name.txt", "alpha.txt"]
    check([sort.index(n) for n in files] == sorted(sort.index(n) for n in files), "size sort order")
    tree = read("tree.out")
    for n in tiny | {".hidden", "child"}:
        check(n in tree, f"tree misses {n}")
    long = read("long.out")
    check("----r-e-" in long and "----rwed" in long, "native protection bits")
    for name, size in [("alpha.txt", 12), ("beta.txt", 6), ("file name.txt", 9), ("zażółć.txt", 3), ("bad\\xff.bin", 4)]:
        line = next(l for l in long.splitlines() if name in l)
        check(re.match(r"[hsparwed?-]{8}\s+" + str(size) + r"\s+\?", line), f"long size of {name}")
    try:
        validate_native_list(read("native-list.txt"), long, tiny | {".hidden"})
    except AssertionError as e:
        failures.append(f"native List comparison: {e}")
    # A trailing "//" names the parent drawer in AmigaDOS: shown as given.
    check(lines("parent-ref.out") == [f"RAM:ez3-qa-{tag}/tiny/sub//"], "parent reference display")
    check(lines("parent-bad.out") == [f"RAM:ez3-qa-{tag}/bad\\xffdir/sub//"], "parent reference with invalid byte")

    # Wide and deep trees, the exact crash command, at 1 MiB and at the default stack.
    for name in ["wide", "wide-l2", "s40-wide"]:
        out = read(name + ".out")
        check(sum(f"d{i:03d}" in out for i in range(160)) == 160, f"{name}: 160 drawers")
        check(out.count("entry") == 160, f"{name}: 160 children")
    for name in ["deep", "s40-deep"]:
        out = read(name + ".out")
        check(out.count("deep-leaf") == 1 and len(re.findall(r"── d$", out, re.M)) == 72, f"{name}: 72 levels and the leaf")
    for name in ["crash-file", "s40-crash"]:
        out = read(name + ".out")
        check("zlib" in out and "LICENSE-MIT" in out and out.count("\n") > 300, f"{name}: licence tree incomplete")

    # Several operands and errors.
    mm = read("multi-missing.out")
    check("RAM:ez3-qa-%s/tiny:" % tag in mm and "f0099.txt" in mm, "later operand after missing one")
    check("No such file" in read("multi-missing.err"), "missing operand reported")
    for name in ["lock-root", "lock-recursive"]:
        check("busy" in read(name + ".err").lower(), f"{name}: lock error reported")
    check("f0099.txt" in read("lock-root.out"), "operand after locked drawer")
    check("zażółć.txt" in read("lock-tree.out") and "zażółć.txt" in read("lock-recursive.out"), "operand after locked tree")
    check("NATIVE_LIST_LOCKED rc=20" in plain, "native List of locked drawer")
    check("No such file" in read("missing-then-lock.err"), "missing-then-lock: missing operand reported")
    check("busy" in read("missing-then-lock.out").lower() or "busy" in read("missing-then-lock.err").lower(), "missing-then-lock: lock reported")

    # Help, version, usage error at the default stack (clap exits through aros::exit).
    check(read("s40-help.out").startswith("A modern replacement for ls"), "help text")
    check("v0.23.5 [+git]" in read("s40-version.out"), "version text")
    check(not read("s40-badopt.out").strip(), "usage error wrote to stdout")
    check("f0099.txt" in read("s40-missing.out"), "default-stack missing operand skipped later operand")

    # Git through libgit2, no git program.
    git_expected = [" - -I .git", "12 -- .gitignore", " 9 -- clean.txt", " 8 -I ignored.txt",
                    " 8 -M modified.txt", " 7 N- staged.txt", "10 -N untracked.txt"]
    for name in ["git-long", "s40-git", "cwd-git"]:
        check(read(name + ".out").splitlines() == git_expected, f"{name}: statuses")
    check(read("git-repos.out").splitlines() == ["- + main git-fixture"], "git-repos")
    # A repository whose .git is at a volume root, and names shown with it.
    check(read("git-root.out").splitlines() == ["9 -- RAM:clean.txt", "8 -M RAM:modified.txt", "7 N- RAM:staged.txt"],
          "repository at a volume root: " + repr(read("git-root.out").splitlines()))
    root_ignore = lines("git-root-ignore.out")
    check("clean.txt" in root_ignore and "ignored.txt" not in root_ignore, "root .gitignore not applied")
    check(lines("posix-dots.out") == ["/alpha.txt", "child"], "POSIX ../ and ./ operands: " + repr(lines("posix-dots.out")))
    check("./nope" in read("posix-missing.err"), "missing POSIX operand not named as typed")
    cwd_long = read("cwd-long.out")
    check("----r-e-" in cwd_long and "?????" not in cwd_long, "protection bits with no operand")
    check(all(n in read("cwd-tree.out") for n in ["alpha.txt", "child"]), "tree with no operand")
    for name in ["git-ignore", "s40-gitignore"]:
        out = read(name + ".out")
        check("ignored.txt" not in out and all(n in out for n in ["clean.txt", "modified.txt", "staged.txt", "untracked.txt"]),
              f"{name}: --git-ignore")
    check("DONE errors=0" in read("gitprobe.txt"), "libgit2 probe")
    check("lookup=PASS" in read("linkprobe.txt"), "Limpet link lookup probe")
    check("icons=268 features=12 grid=8x17 clipped=0" in read("iconprobe.txt"), "icon font probe")

    check(hold is not None, "hold probe results not given")
    if hold:
        log = (hold / f"ecrash-rust-hold-{hold_tag}.txt").read_text()
        check(log.rstrip().endswith("BEFORE 124 RAM:eza-dirprobe-997b9f64/d124") and "AFTER 123 entries=1" in log,
              "Rust hold probe did not stop at d124")
    for kind in ["c", "rust"]:
        check((dst / f"ecrash-{kind}-scan-{tag}.txt").read_text().rstrip().endswith("DONE failures=0"), f"{kind} scan probe")

    # Timing summary, same boot.
    rich = read("rich-report.txt")
    def series(pattern):
        return [int(m) for m in re.findall(pattern, rich)]
    rows = []
    for size, n in [("small", 100), ("large", 2000)]:
        rows.append((size, n,
            statistics.median(series(r"TIME read %s rep=\d entries=\d+ ticks=(\d+)" % size)),
            statistics.median(series(r"CASE t\d-nil1-%s rc=0 expected=0 ticks=(\d+)" % size)),
            statistics.median(series(r"CASE t\d-nill-%s rc=0 expected=0 ticks=(\d+)" % size)),
            statistics.median(series(r"CASE t\d-terml-%s rc=0 expected=0 ticks=(\d+)" % size)),
            statistics.median(series(r"TIME type-l %s rep=\d rc=0 ticks=(\d+)" % size))))
    start = statistics.median(series(r"CASE t\d-start rc=0 expected=0 ticks=(\d+)"))
    print(f"start-up (--version to NIL:): {start / 50:.2f} s")
    print("entries | read+stat | eza -1 NIL: | eza -l NIL: | eza -l Limpet | Type of -l text to Limpet")
    for size, n, r, n1, nl, tl, ty in rows:
        print(f"{n:7d} | {r/50:9.2f} | {n1/50:11.2f} | {nl/50:11.2f} | {tl/50:13.2f} | {ty/50:.2f}")

    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("PASS: all acceptance assertions")

if __name__ == "__main__":
    main()
