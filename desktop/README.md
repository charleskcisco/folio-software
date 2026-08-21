# Tauri + Vanilla TS

This template should help get you started developing with Tauri in vanilla HTML, CSS and Typescript.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)

## Building for Intel Macs

Intel builds are made here, not on CI: `macos-13` was retired and every
replacement Intel runner is a "larger runner", which GitHub bills even on
public repositories. Rosetta does the job for nothing.

PyInstaller freezes for the architecture of the interpreter running it, so
the Intel build needs an x86_64 Python and x86_64 copies of pandoc and
typst. They live in `builds/intel-toolchain/` (untracked, ~180MB) and are
reconstructible from:

- `astral-sh/python-build-standalone` — cpython 3.12 x86_64-apple-darwin
  (3.12 to match CI; the version the binary embeds is the version students
  run, so it should not differ between architectures)
- `jgm/pandoc` — pandoc 3.10 x86_64-macOS
- `typst/typst` — typst v0.15.1 x86_64-apple-darwin

Then:

```
arch -x86_64 env \
  FOLIO_PYTHON="$PWD/builds/intel-toolchain/python/bin/python3.12" \
  FOLIO_TOOLS_DIR="$PWD/builds/intel-toolchain/bin" \
  ./freeze.sh
cd desktop && APPLE_SIGNING_IDENTITY="..." npm run tauri build -- --target x86_64-apple-darwin
```

freeze.sh reads the frozen binary's architecture with `lipo` and names the
sidecar accordingly, so a cross build cannot end up staged under the host's
triple. It also refreshes only the copies belonging to the target it built,
which is what stops an Intel freeze from leaving the native app running an
x86_64 sidecar under Rosetta.

## Signing (macOS)

The signing identity is **not** in `tauri.conf.json`. It names a
certificate in one particular keychain, so committing it makes the build
depend on the machine it was written on -- CI has no such certificate and
fails with "The specified item could not be found in the keychain".

Pass it in the environment instead, and an unsigned build is simply the
default everywhere else:

```
APPLE_SIGNING_IDENTITY="Developer ID Application: NAME (TEAMID)" \
  npm run tauri build
```

`security find-identity -v -p codesigning` lists the identities available.
Note the Team ID is the certificate's **OU** field, not the value in
parentheses after the name -- those differ on a Development certificate,
and `notarytool` rejects the wrong one with an unhelpful 403.


`src-tauri/entitlements.plist` grants one entitlement,
`com.apple.security.cs.disable-library-validation`. Folio is a PyInstaller
onefile binary: at launch it unpacks Python and its `.so` files into a temp
directory and loads them from there. Under the hardened runtime, library
validation refuses to load code not signed by the same team, so without
this the app signs cleanly, notarises cleanly, and then dies the instant it
starts.

**Do not put XML comments in that file.** Apple's entitlements parser
(AMFI) is stricter than a normal plist parser and rejects them outright —
`codesign` fails with `AMFIUnserializeXML: syntax error`, and Tauri reports
only "failed to sign app", which points nowhere near the real cause. That
is why the explanation lives here instead.
