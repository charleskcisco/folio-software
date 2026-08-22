mod pty;

use pty::PtySession;

/// Where the frozen Folio binary lives.
///
/// Bundled, it is a Tauri sidecar: declared as an externalBin, named with
/// the target triple in the repo, and placed beside the app executable
/// with the triple stripped. Resolving it from `current_exe` is what makes
/// the app portable -- it holds wherever the bundle is copied to, and it
/// is the same shape on every platform, so Windows needs no special case
/// beyond the .exe suffix.
///
/// It was previously a bundle.resources entry, which Tauri rewrote from
/// `../../dist/folio` to `Contents/Resources/_up_/_up_/dist/folio`. The
/// lookup expected `Contents/Resources/folio`, missed, and fell through to
/// the development path below -- an absolute path into the source tree,
/// baked in at compile time. The .app ran perfectly on the machine that
/// built it and could not have run anywhere else.
fn folio_binary() -> String {
    let name = if cfg!(target_os = "windows") { "folio.exe" } else { "folio" };

    if let Ok(exe) = std::env::current_exe() {
        if let Some(sidecar) = exe.parent().map(|d| d.join(name)) {
            if sidecar.is_file() {
                return sidecar.to_string_lossy().into_owned();
            }
        }
    }

    // Development: ../dist/folio relative to the desktop/ directory, so
    // `npm run tauri dev` works against a source checkout.
    let dev = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.join("dist").join(name));
    match dev {
        Some(p) if p.is_file() => p.to_string_lossy().into_owned(),
        _ => name.to_string(),
    }
}

#[tauri::command(async)]
fn folio_path() -> String {
    folio_binary()
}

/// Paint the window -- and with a transparent title bar, the title bar --
/// in the matte colour.
///
/// This is what makes the window read as a frame around Folio rather than
/// a container that not quite matches it. The colour comes from the
/// running app's own scheme, so the frame follows whatever the user picks
/// inside Folio instead of the wrapper keeping a second palette that can
/// drift out of step.
#[tauri::command(async)]
fn set_window_background(window: tauri::WebviewWindow, color: String) -> Result<(), String> {
    let h = color.trim_start_matches('#');
    if h.len() != 6 {
        return Err(format!("expected #rrggbb, got {color:?}"));
    }
    let byte = |i: usize| u8::from_str_radix(&h[i..i + 2], 16).map_err(|e| e.to_string());
    let c = tauri::utils::config::Color(byte(0)?, byte(2)?, byte(4)?, 255);
    window
        .set_background_color(Some(c))
        .map_err(|e| e.to_string())
}

/// Turn off macOS Writing Tools for this window.
///
/// Apple Intelligence puts a floating "Write with Siri" affordance beside
/// the insertion point in any editable text. Folio is a full-screen
/// terminal application that paints every cell itself, so the button
/// hovers over the document, follows the cursor, and covers whatever
/// character is underneath it -- there is no layout for it to sit in.
///
/// WKWebView has `writingToolsBehavior` for exactly this, but Tauri does
/// not surface it, hence the raw message send through `with_webview`.
/// Guarded by respondsToSelector: the property is macOS 15+, and on an
/// older system this would otherwise be an unrecognised selector, which
/// is a crash rather than a missing feature.
#[cfg(target_os = "macos")]
fn disable_writing_tools(window: &tauri::WebviewWindow) {
    use objc2::runtime::AnyObject;
    use objc2::{msg_send, sel};

    // Reported rather than swallowed. Both failure paths here are silent
    // by nature -- with_webview can error, and respondsToSelector can be
    // false -- and a silent no-op looks identical to a fix that worked.
    //
    // Deliberately minimal: objc2's msg_send! verifies method signatures
    // against the runtime under debug_assertions, so introspection that
    // looks harmless (asking an object for its class name) aborts the
    // process on a type mismatch. Only the two calls that must happen
    // happen here.
    let outcome = window.with_webview(|wv| unsafe {
        let webview = wv.inner() as *mut AnyObject;
        if webview.is_null() {
            eprintln!("[folio] writing tools: webview pointer was null");
            return;
        }
        let responds: bool = msg_send![webview, respondsToSelector: sel!(setWritingToolsBehavior:)];
        if !responds {
            eprintln!("[folio] writing tools: webview does not respond to \
                       setWritingToolsBehavior:; affordance left enabled");
            return;
        }
        // NSWritingToolsBehaviorNone
        let _: () = msg_send![webview, setWritingToolsBehavior: -1isize];
        eprintln!("[folio] writing tools: disabled");
    });
    if let Err(e) = outcome {
        eprintln!("[folio] writing tools: with_webview failed: {e}");
    }
}

/// Log panics before they reach a frame that cannot unwind.
///
/// The abort message at that boundary is always "panic in a function that
/// cannot unwind" -- the original message and location are gone by then.
/// This hook runs first and keeps them.
fn install_panic_logger() {
    let default = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let msg = format!("[folio] panic: {info}\n");
        eprint!("{msg}");
        // Beside the config, not in temp_dir(): on macOS that is a
        // per-session /var/folders path that differs between a launch from
        // the shell and one from Finder, so a crash report would be
        // somewhere different every time.
        if let Some(log) = dirs_next::home_dir()
            .map(|h| h.join(".config").join("folio").join("desktop-panic.log"))
        {
            let _ = std::fs::create_dir_all(log.parent().unwrap());
            if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(log) {
                use std::io::Write;
                let _ = f.write_all(msg.as_bytes());
            }
        }
        default(info);
    }));
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    install_panic_logger();
    #[allow(unused_mut)]
    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init());

    // macOS only: replace the default menu.
    //
    // The stock menu binds Cmd+Z to its own Undo and Cmd+Z never reaches
    // the webview, so Folio's undo is unreachable from the shortcut every
    // Mac user will try first. Same for Redo. Cut/copy/paste/select-all
    // stay, because those really are the system's to handle and the
    // frontend deliberately does not intercept them.
    //
    // Not applied elsewhere: Windows and Linux have no default menu, and
    // adding one would put a menu bar on a window whose whole point is
    // that it has no chrome.
    #[cfg(target_os = "macos")]
    {
        use tauri::menu::{Menu, PredefinedMenuItem, Submenu};
        builder = builder.menu(|h| {
            let app = Submenu::with_items(
                h,
                "Folio",
                true,
                &[
                    &PredefinedMenuItem::about(h, None, None)?,
                    &PredefinedMenuItem::separator(h)?,
                    &PredefinedMenuItem::hide(h, None)?,
                    &PredefinedMenuItem::hide_others(h, None)?,
                    &PredefinedMenuItem::separator(h)?,
                    &PredefinedMenuItem::quit(h, None)?,
                ],
            )?;
            let edit = Submenu::with_items(
                h,
                "Edit",
                true,
                &[
                    &PredefinedMenuItem::cut(h, None)?,
                    &PredefinedMenuItem::copy(h, None)?,
                    &PredefinedMenuItem::paste(h, None)?,
                    &PredefinedMenuItem::select_all(h, None)?,
                ],
            )?;
            Menu::with_items(h, &[&app, &edit])
        });
    }

    builder
        .setup(|_app| {
            #[cfg(target_os = "macos")]
            {
                use tauri::Manager;
                if let Some(w) = _app.get_webview_window("main") {
                    disable_writing_tools(&w);
                }
            }
            Ok(())
        })
        .manage(PtySession::default())
        .invoke_handler(tauri::generate_handler![
            folio_path,
            set_window_background,
            pty::pty_start,
            pty::pty_write,
            pty::pty_resize,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
