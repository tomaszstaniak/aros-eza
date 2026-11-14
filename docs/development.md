# Build and verification

Requires Python 3.12+, Git, rustup, an existing rust-aros-compatible nightly
sysroot, and matching x86_64 ABIv11 GCC/SDK. No shared toolchain is installed
or replaced. eza requires Rust >=1.90, edition 2024.

Clone the URL in upstreams.json into upstream/eza and check out its full commit.
Copy local.example.json to ignored local.json and supply local paths. Environment
EZA_AROS_GCC, EZA_AROS_AR, EZA_AROS_SDK, EZA_RUST_AROS and EZA_TOOLCHAIN override
that file. Invoke scripts from any directory; local paths should be absolute.

```
python3 scripts/eza.py materialize
python3 scripts/eza.py test
python3 scripts/eza.py verify
python3 scripts/eza.py build --build-root build/final-a
python3 scripts/eza.py rebuild --build-root build/final-b
python3 scripts/eza.py native --build-root build/final-a
python3 scripts/package.py --build-root build/final-a --output-name NAME.zip
```

`build` verifies that work/eza equals an isolated reconstruction of the patch
series, copies that source into `<root>/src`, and builds there with its own
Cargo home and target directory. `rebuild` first reconstructs the source in a
temporary directory and refuses an existing root. Two roots built this way
give byte-identical executables; compare `binary_sha256` in each
`identity.json`.

What makes that hold, and why each piece exists:

- the generated libc-aros and the patched libgit2-sys live under
  `<root>/src/target/aros-deps`, inside the workspace, because Cargo hashes
  the absolute path of a path dependency outside the workspace into every
  dependent crate;
- std's own libc (build-std resolves it in the sysroot's library workspace)
  is the exception: each build generates and checks its copy, then uses one
  immutable copy per content hash under `build/targets/libc-dual-<sha>`; the
  target specification is kept the same way under `build/targets/<sha>`.
  Reproducibility therefore holds for one checkout location;
- `-Ztrim-paths` with `profile.release.trim-paths="all"` removes the build
  root from Rust panic locations. `--remap-path-prefix` cannot do that: its
  root-specific value would enter every metadata hash. C sources get
  `-ffile-prefix-map` through CFLAGS;
- `LIBZ_SYS_STATIC=1` builds libz-sys's bundled zlib. Otherwise it links the
  SDK's `libz.a`, a stub that opens z1.library at start-up; package.py
  refuses an executable that still names z1.library.

The source recipe consumes rust-aros e8e267dd0be6857d221b29b4ee8c7a5eaef92167
(libc-dual tool, libc-aros, target template and presentation SDK). The
release profile overrides upstream strip=true: full stripping breaks AROS
relocations. Git support is built in through the patched libgit2-sys
(patches/deps), for local repositories only. Rayon is excluded on AROS.

`native` builds the guest test programs from the same inputs as the
executable in that root: `acceptance` (tests/native/acceptance.c), the
directory probes and `git_status`, which links the same libgit2 and zlib
archives as eza. Hashes go to `<root>/probes/probes.json`.

Host tests (`test`) cover the capability policy, output filtering, URIs,
AmigaDOS names, build-input staging and the native checker. The upstream
suite runs with `cargo test --locked` and both path patches;
`tests/tree_fd_regression.py` runs a host eza under a 64-descriptor limit.
None of them establishes native behaviour.

Native acceptance runs from the final ZIP on AROS One: stage a directory with
the ZIP, the probes, `tests/native/fixtures/*` and the `c8-*.aros` scripts,
extract it to RAM:, run `c8-plain.aros` from an ordinary Shell and
`c8-rich.aros` from Limpet, then check with
`python3 tests/check_acceptance.py RESULTS-DIR TAG HOLD-RESULTS-DIR`.
Result names carry a per-run tag and must never repeat on RESULTS:.

Packaging requires `rust_notices` in local.json (or EZA_RUST_NOTICES). The ZIP
holds the modified eza source, the pinned Rust/libc/SDK inputs, the patched
libgit2-sys source with its archive and patch, and runtime and dependency
notices. `dist/` is append-only: an existing archive name is refused and
SHA256SUMS only gains lines.

## Mainline AROS (ABIv1)

`scripts/build_target.py` builds the mainline executables for x86_64 PC and
for the Raspberry Pi (AArch64). Both follow the recipe of the other Rust ports
built with rust-aros: a unix target profile (`profiles/x86_64-v1-pc.json`,
`profiles/aarch64-v1-raspi-unix.json`) and `std-groundwork/libc-aros` of the
rust-aros commit named in the local file, with the patches in
`patches/platform/libc-aros`, wrapped by `tools/libc-dual.py` so that build
scripts compiled for the host keep the registry libc. Copy
`local.v1.example.json` or `local.raspi.example.json`, fill in the paths, then:

```
python3 scripts/build_target.py --target aros-x86_64-abiv1-pc --local local.v1.json
python3 scripts/release.py aros-x86_64-abiv1-pc REVISION
```

The Pi build needs a toolchain made by rust-aros `tools/common-sysroot.py` at
42e16d9 or later. Its C compiler is Clang, which refuses implicit function
declarations: `patches/deps/libgit2-sys-0.18.5-aros-process.patch` compiles
out libgit2's helper-program code (`fork`, `sigwait`), which a local-repository
build never reaches.

The result and its record are `build/<target>/eza` and `identity.json`. This
recipe is not the byte-reproducible one of the ABIv11 build. `release.py`
makes the apkg archives in `dist/` for both targets.
