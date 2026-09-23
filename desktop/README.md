# Tauri + Vanilla TS

This template should help get you started developing with Tauri in vanilla HTML, CSS and Typescript.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)

## How Folio is packaged

Folio is frozen by `../freeze.sh` into a folder (PyInstaller `--onedir`),
staged at `src-tauri/folio-dist/`, and shipped as a bundle resource:
`Contents/Resources/folio/` on macOS, `folio\` beside the app on Windows.
`lib.rs` resolves it from the resource directory.

It was originally a single `--onefile` executable. That is a
self-extracting archive: every launch unpacked ~190MB into a fresh temp
directory before Folio ran, which was the 3-5 seconds of blank window at
startup, and a launch that was killed rather than quit left the directory
behind. The folder starts in under 0.2s (after macOS has scanned a new
install once) and writes nothing to temp.

`folio-dist/TRIPLE` records the architecture the folder holds, and
`build.rs` refuses to build for any other target. freeze.sh reads the
architecture off the frozen binary with `lipo` rather than assuming the
host's, and refreshes only the copies under `target/` belonging to that
architecture, so an Intel freeze cannot leave the native dev app running
an x86_64 Folio under Rosetta.

## Python toolchains (macOS)

Both Mac builds freeze with **python-build-standalone**, not Homebrew or
python.org. Those are framework builds: a folder frozen from one carries
`Python.framework`, symlinks and ~60 binaries that each need signing, and
freeze.sh refuses it. A standalone Python freezes to four binaries (five
with Homebrew's pandoc, which brings `libgmp`) in a plain folder.

The toolchains live in `builds/` (untracked) and freeze.sh uses the one
matching the architecture it runs as, with no environment variables:

| Toolchain | Contents |
| --- | --- |
| `builds/arm64-toolchain/` | `python/` — cpython 3.12 aarch64-apple-darwin |
| `builds/intel-toolchain/` | `python/` — cpython 3.12 x86_64-apple-darwin; `bin/` — pandoc 3.10 x86_64-macOS, typst v0.15.1 x86_64-apple-darwin |

The Pythons come from `astral-sh/python-build-standalone` (the
`install_only` archives), then `python3.12 -m pip install prompt_toolkit
pygments pyinstaller pytest`. 3.12 matches CI: the version the binary
embeds is the version students run, so it should not differ between
architectures. pandoc and typst come from `jgm/pandoc` and
`typst/typst` releases. A toolchain without `bin/` falls back to the
pandoc and typst on `PATH`.

## Building for Intel Macs

Intel builds are made here, not on CI: `macos-13` was retired and every
replacement Intel runner is a "larger runner", which GitHub bills even on
public repositories. Rosetta does the job for nothing:

```
arch -x86_64 ./freeze.sh
cd desktop && APPLE_SIGNING_IDENTITY="..." npm run tauri build -- --target x86_64-apple-darwin
```

Re-run plain `./freeze.sh` afterwards before going back to the native app:
only one architecture is staged at a time, and `build.rs` will say so if
you forget.

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
`com.apple.security.cs.disable-library-validation`, to the frozen `folio`
executable. It is kept from the onefile days, when Python and its
libraries were unpacked into a temp directory and loaded from there, and
library validation killed the process the instant it started. The folder
layout loads a `libpython` signed by the same team, so it may no longer be
needed -- but removing it means another notarization round-trip to find
out, for no gain a student would notice.

Tauri signs the app and nothing inside its resources, so
`scripts/sign-folio.mjs` runs as the `beforeBundleCommand` and signs every
Mach-O file in `folio-dist/` with the same identity, the hardened runtime
and a timestamp. Without it the binaries keep PyInstaller's ad-hoc
signature and notarization rejects the app. It does nothing when
`APPLE_SIGNING_IDENTITY` is unset.

**Do not put XML comments in that file.** Apple's entitlements parser
(AMFI) is stricter than a normal plist parser and rejects them outright —
`codesign` fails with `AMFIUnserializeXML: syntax error`, and Tauri reports
only "failed to sign app", which points nowhere near the real cause. That
is why the explanation lives here instead.

## macOS Writing Tools cannot be disabled from the app

Apple Intelligence puts a floating "Writing Tools" button beside the
insertion point in any editable text. In Folio it hovers over the grid and
covers whatever character is under it, because a terminal that paints
every cell has no empty layout for it to sit in.

There is no way to switch it off from inside the application. Both routes
were tried and neither works:

- **`writingsuggestions="false"`** on the focused element. This is the
  documented web-side control, and Writing Tools ignores it. Reapplying it
  on mutation, on focus, and on window activation makes no difference.
- **`writingToolsBehavior` on the web view.** This property belongs to
  `NSTextView`, not `WKWebView`. Confirmed by asking the ObjC runtime:
  `wry`'s `WryWebView` is a `WKWebView` subclass and does not respond to
  `setWritingToolsBehavior:`.

And the system's own off switch does not reach it either. With Apple
Intelligence disabled through Screen Time content restrictions, every
native application on the machine stopped showing the button and Folio did
not -- in the signed, notarized build as well as the development one, so
it is not an artifact of ad-hoc signing.

That is the whole finding: the restriction is not propagating to WebKit's
Writing Tools integration. It is a gap on Apple's side, not a switch we
have failed to find, and no application-level code can out-rank a system
restriction that is already being ignored.

Nothing further was attempted, and nothing should be without new
information -- the remaining ideas (private WebKit API, making xterm's
input textarea non-editable) trade a floating button for a broken editor.
Worth a Feedback Assistant report if it starts mattering.
