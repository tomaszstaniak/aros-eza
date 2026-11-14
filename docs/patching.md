# Patching

The manifest pins eza v0.23.5. Keep upstream/eza clean. Materialize a new work/eza from that commit, then apply patches/eza/series in order with git apply. An empty series reproduces upstream unchanged. Do not replace an existing work tree: preserve unsaved files, branches, stashes and reflogs first. Verification must reconstruct in a separate directory and compare file contents and modes. Patch headers record base, rationale, scope, status, verification and removal condition.
