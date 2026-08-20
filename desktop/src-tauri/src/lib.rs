mod pty;

use pty::PtySession;

/// Where the frozen Folio binary lives.
///
/// In a bundled app it is a Tauri sidecar, stored beside the executable
/// under a target-triple name -- pandoc-aarch64-apple-darwin rather than
/// pandoc. Resolving that is the Rust side's job; the Python side reads
/// FOLIO_PANDOC / FOLIO_TYPST and never learns about triples.
///
/// In development there is no bundle, so fall back to the freeze output
/// in dist/ and let `npm run tauri dev` work against a source checkout.
fn folio_binary(app: &tauri::AppHandle) -> String {
    use tauri::Manager;
    if let Ok(dir) = app.path().resource_dir() {
        let bundled = dir.join("folio");
        if bundled.is_file() {
            return bundled.to_string_lossy().into_owned();
        }
    }
    // Development: ../dist/folio relative to the desktop/ directory.
    let dev = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.join("dist").join("folio"));
    match dev {
        Some(p) if p.is_file() => p.to_string_lossy().into_owned(),
        _ => "folio".to_string(),
    }
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

#[tauri::command(async)]
fn folio_path(app: tauri::AppHandle) -> String {
    folio_binary(&app)
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

    let _ = window.with_webview(|wv| unsafe {
        let webview = wv.inner() as *mut AnyObject;
        if webview.is_null() {
            return;
        }
        let responds: bool = msg_send![webview, respondsToSelector: sel!(setWritingToolsBehavior:)];
        if responds {
            // NSWritingToolsBehaviorNone
            let _: () = msg_send![webview, setWritingToolsBehavior: -1isize];
        }
    });
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
