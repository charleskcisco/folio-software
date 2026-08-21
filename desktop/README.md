# Tauri + Vanilla TS

This template should help get you started developing with Tauri in vanilla HTML, CSS and Typescript.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)

## Signing (macOS)

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
