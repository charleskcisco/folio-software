//! The bridge between the webview terminal and the Folio process.
//!
//! Folio is a full-screen prompt_toolkit application. It expects a real
//! terminal: a pty it can query for size, put in raw mode, and drive with
//! escape sequences. So the wrapper does not reimplement an editor -- it
//! opens a pty, spawns the frozen binary on the far end, and moves bytes.

use std::io::{Read, Write};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use portable_pty::{CommandBuilder, NativePtySystem, PtySize, PtySystem};
use tauri::ipc::Channel;

/// The writer half, kept so keystrokes and resizes can reach the child.
pub struct PtySession {
    writer: Mutex<Option<Box<dyn Write + Send>>>,
    master: Mutex<Option<Box<dyn portable_pty::MasterPty + Send>>>,
    /// Kept so a previous Folio can be shut down before a new one starts,
    /// and so the reader thread can collect the exit status.
    child: Arc<Mutex<Option<Box<dyn portable_pty::Child + Send + Sync>>>>,
    /// Bumped on every start. A reader thread reports its child's exit only
    /// while it is still the current session, so a deliberate teardown does
    /// not look like Folio falling over.
    generation: Arc<AtomicU64>,
}

impl Default for PtySession {
    fn default() -> Self {
        Self {
            writer: Mutex::new(None),
            master: Mutex::new(None),
            child: Arc::new(Mutex::new(None)),
            generation: Arc::new(AtomicU64::new(0)),
        }
    }
}

/// End the current session, if there is one.
///
/// Without this every call to `pty_start` leaks the session before it: the
/// frontend reloads -- a dev HMR reload, or any webview reload in a real
/// build -- `start()` runs again, and another Folio appears while the old
/// one keeps running with the same vault open. Several instances then
/// autosave over each other's entries, which is a corruption risk, not an
/// untidiness. Killing the child first is what makes `pty_start`
/// repeatable.
fn stop_existing(state: &PtySession) {
    // Anything the outgoing reader thread reports from here on is the
    // result of this teardown, not news about Folio.
    state.generation.fetch_add(1, Ordering::SeqCst);
    // Drop the handles first so the child's terminal hangs up.
    if let Ok(mut w) = state.writer.lock() {
        w.take();
    }
    if let Ok(mut m) = state.master.lock() {
        m.take();
    }
    // Then make sure it is actually gone, and reap it so it leaves no
    // zombie behind. A hung-up prompt_toolkit app usually exits on its
    // own; "usually" is not good enough to rely on here.
    if let Ok(mut c) = state.child.lock() {
        if let Some(mut child) = c.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Start Folio on a pty and stream its output to the frontend.
///
/// `on_output` is a Channel rather than an event emit. Tauri's default
/// IPC serialises through JSON, which is the wrong shape for a terminal:
/// a redraw storm or a fast paste turns into thousands of JSON documents.
/// Channel is the supported path for streaming bytes.
// Deliberately `command(async)` and not a bare `command`. Tauri runs a
// synchronous command on the main thread, which on macOS means it runs
// inside the AppKit event dispatch that tao drives. A panic there hits an
// `extern "C"` frame it cannot unwind through, so the process aborts
// instead of returning an Err to the frontend -- the whole app dies over
// one bad keystroke. `async` on a non-async fn moves the body to a worker
// thread, where a panic is caught and surfaces as an IPC error. It also
// keeps a blocking pty write off the thread that has to drain the child's
// output, which would otherwise deadlock the two against each other.
#[tauri::command(async)]
pub fn pty_start(
    state: tauri::State<'_, PtySession>,
    program: String,
    args: Vec<String>,
    cols: u16,
    rows: u16,
    on_output: Channel<Vec<u8>>,
    on_exit: Channel<i32>,
) -> Result<(), String> {
    stop_existing(&state);

    let pty = NativePtySystem::default();
    let pair = pty
        .openpty(PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
        .map_err(|e| format!("openpty: {e}"))?;

    let mut cmd = CommandBuilder::new(&program);
    for a in &args {
        cmd.arg(a);
    }

    // Windows defaults stdout to the console codepage, and under ConPTY
    // prompt_toolkit may write through sys.stdout rather than the Win32
    // console API. If that stream is cp1252 every box-drawing character
    // in the chrome mangles. Deliberately not PYTHONUTF8, which would
    // also change the default *file* encoding and mask a class of export
    // bug the test suite exists to catch.
    cmd.env("PYTHONIOENCODING", "utf-8");
    cmd.env("TERM", "xterm-256color");
    // Tell Folio it is in the wrapper, not on the deck. It uses this to
    // hide controls that only mean something on the device, and to show
    // Cmd rather than Ctrl in the guide on macOS.
    cmd.env("FOLIO_HOST", "desktop");

    let child = pair
        .slave
        .spawn_command(cmd)
        .map_err(|e| format!("spawn {program}: {e}"))?;
    drop(pair.slave);

    let mut reader = pair
        .master
        .try_clone_reader()
        .map_err(|e| format!("clone reader: {e}"))?;
    let writer = pair
        .master
        .take_writer()
        .map_err(|e| format!("take writer: {e}"))?;

    *state.child.lock().map_err(|_| "child lock poisoned")? = Some(child);
    *state.writer.lock().map_err(|_| "writer lock poisoned")? = Some(writer);
    *state.master.lock().map_err(|_| "master lock poisoned")? = Some(pair.master);

    let channel = Arc::new(on_output);
    let child_handle = Arc::clone(&state.child);
    let generation = Arc::clone(&state.generation);
    let my_generation = generation.load(Ordering::SeqCst);

    std::thread::spawn(move || {
        let mut buf = [0u8; 8192];
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    if channel.send(buf[..n].to_vec()).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }

        // Folio has gone. Collect the status and tell the frontend, which
        // owns the decision about what an exit means -- a vault change
        // asks for a relaunch, anything else is news the user needs. Left
        // unreported, the window is simply blank, which is what a vault
        // switch used to look like.
        if generation.load(Ordering::SeqCst) != my_generation {
            return; // superseded by a deliberate restart
        }
        let status = child_handle
            .lock()
            .ok()
            .and_then(|mut c| c.take())
            .and_then(|mut ch| ch.wait().ok())
            .map(|st| st.exit_code() as i32)
            .unwrap_or(-1);
        if generation.load(Ordering::SeqCst) == my_generation {
            let _ = on_exit.send(status);
        }
    });

    Ok(())
}

/// Keystrokes, straight through. No interpretation here: the app owns
/// its own key handling and the wrapper must not second-guess it.
#[tauri::command(async)]
pub fn pty_write(state: tauri::State<'_, PtySession>, data: Vec<u8>) -> Result<(), String> {
    let mut guard = state.writer.lock().map_err(|_| "writer lock poisoned")?;
    let writer = guard.as_mut().ok_or("pty not started")?;
    writer.write_all(&data).map_err(|e| e.to_string())?;
    writer.flush().map_err(|e| e.to_string())
}

/// Resize both halves.
///
/// This has to reach the pty, not just xterm.js: Folio reads the terminal
/// size at runtime and switches between two chromes at 120 columns. A
/// resize the pty never hears about means the layout changes at the wrong
/// moment, or does not change at all.
#[tauri::command(async)]
pub fn pty_resize(
    state: tauri::State<'_, PtySession>,
    cols: u16,
    rows: u16,
) -> Result<(), String> {
    let guard = state.master.lock().map_err(|_| "master lock poisoned")?;
    let master = guard.as_ref().ok_or("pty not started")?;
    master
        .resize(PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
        .map_err(|e| e.to_string())
}
