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
