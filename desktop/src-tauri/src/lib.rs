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
        .setup(|app| {
            // The window is built here rather than taken straight from
            // tauri.conf.json (which sets create: false) so that a
            // WKWebViewConfiguration can be attached to it.
            //
            // That configuration is the only way to decline Apple
            // Intelligence Writing Tools. writingToolsBehavior lives on
            // WKWebViewConfiguration, not on WKWebView, and it is read
            // when the web view is constructed -- so it cannot be set
            // afterwards. Every earlier attempt failed for that reason:
            // the web view genuinely does not respond to the selector,
            // because by then the decision has already been made.
            #[cfg(target_os = "macos")]
            {
                use objc2::msg_send;
                use objc2::MainThreadMarker;
                use objc2_web_kit::WKWebViewConfiguration;

                let config = app
                    .config()
                    .app
                    .windows
                    .iter()
                    .find(|w| w.label == "main")
                    .cloned()
                    .ok_or("no window labelled 'main' in tauri.conf.json")?;

                // setup() runs on the main thread, which is where AppKit
                // objects must be created.
                let mtm = MainThreadMarker::new()
                    .ok_or("setup() was not on the main thread")?;
                let wk_config = unsafe { WKWebViewConfiguration::new(mtm) };
                // NSWritingToolsBehaviorNone
                let _: () = unsafe { msg_send![&*wk_config, setWritingToolsBehavior: -1isize] };

                tauri::WebviewWindowBuilder::from_config(app, &config)?
                    .with_webview_configuration(wk_config)
                    .build()?;
            }

            #[cfg(not(target_os = "macos"))]
            {
                let config = app
                    .config()
                    .app
                    .windows
                    .iter()
                    .find(|w| w.label == "main")
                    .cloned()
                    .ok_or("no window labelled 'main' in tauri.conf.json")?;
                tauri::WebviewWindowBuilder::from_config(app, &config)?.build()?;
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
