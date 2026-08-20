import { invoke, Channel } from "@tauri-apps/api/core";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebglAddon } from "@xterm/addon-webgl";
import "@xterm/xterm/css/xterm.css";

// JetBrains Mono, bundled rather than assumed. A terminal grid needs a
// genuinely monospaced face: xterm.js measures one glyph and lays every
// cell out on that width, so a proportional font -- De Gruyter Serif, say,
// which is here for the PDF output and not for this -- leaves every
// character fractionally off its cell. Regular, bold and italic are all
// loaded because Folio uses all three in its chrome.
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/400-italic.css";
import "@fontsource/jetbrains-mono/700.css";
import "@fontsource/jetbrains-mono/700-italic.css";
import "./styles.css";

const FONT = '"JetBrains Mono", ui-monospace, Menlo, monospace';
const FONT_STEPS = [10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24];
const FONT_SIZE = Number(localStorage.getItem("folio.fontSize")) || 15;

const term = new Terminal({
  fontFamily: FONT,
  fontSize: FONT_SIZE,
  lineHeight: 1.25,
  cursorBlink: true,
  // The wrapper owns the whole window; nothing else is competing for it.
  scrollback: 0,
  // Folio's own dark theme, matched exactly (folio.py's style table:
  // "#e0e0e0 bg:#2a2a2a"). The app repaints every cell itself, so these
  // matter in two places only -- the instant before the first paint, and
  // the cursor, which xterm draws rather than the app. The previous cream
  // values meant a dark cursor on a dark background, i.e. no visible
  // cursor at all.
  theme: {
    background: "#2a2a2a",
    foreground: "#e0e0e0",
    cursor: "#e0e0e0",
    cursorAccent: "#2a2a2a",
    selectionBackground: "#4a4a4a",
  },
});

const fit = new FitAddon();
term.loadAddon(fit);

// The matte.
//
// The window is a frame around Folio, not a container that almost matches
// it: one colour from the title bar down, with the grid inset in the
// middle like a page on a desk. This also absorbs the few leftover pixels
// at the right and bottom that the grid can never fill -- `fit` floors to
// whole cells -- so a rounding artefact reads as a margin instead of a
// ragged edge.
//
// The colours are not ours. Folio announces its own scheme over OSC 10 and
// 11 (the standard way a full-screen program tells a terminal its
// foreground and background), so the frame follows whatever scheme the
// user picks inside the app, and the wrapper never keeps a second copy of
// the palette that could drift out of step with folio.py's.
let pageFg = "#e0e0e0";
let pageBg = "#2a2a2a";

const mix = (a: string, b: string, t: number) => {
  const parts = (h: string) =>
    [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [parts(a), parts(b)];
  const chan = (i: number) =>
    Math.round(x[i] + (y[i] - x[i]) * t)
      .toString(16)
      .padStart(2, "0");
  return `#${chan(0)}${chan(1)}${chan(2)}`;
};

function applyTheme() {
  // Toward the foreground rather than a fixed darkening: on a dark scheme
  // that lifts the frame slightly, on a light one it deepens it, and both
  // read as a frame without a second rule.
  const matte = mix(pageBg, pageFg, 0.1);
  document.body.style.background = matte;
  const host = document.getElementById("terminal");
  if (host) host.style.background = pageBg;
  invoke("set_window_background", { color: matte }).catch(() => {
    /* frame stays as configured; not worth failing a keystroke over */
  });
}

const readColor = (data: string) => {
  const m = /#([0-9a-f]{6})/i.exec(data.trim());
  return m ? `#${m[1].toLowerCase()}` : null;
};

// `false` so xterm's own handler still runs and repaints the grid; we are
// observing these, not taking them over.
term.parser.registerOscHandler(10, (data) => {
  const c = readColor(data);
  if (c) {
    pageFg = c;
    applyTheme();
  }
  return false;
});
term.parser.registerOscHandler(11, (data) => {
  const c = readColor(data);
  if (c) {
    pageBg = c;
    applyTheme();
  }
  return false;
});

// Bytes from the pty. A Channel rather than an event listener: the
// default IPC serialises through JSON, which a redraw storm turns into
// thousands of documents.
const output = new Channel<number[]>();
output.onmessage = (chunk) => term.write(new Uint8Array(chunk));

const encoder = new TextEncoder();
const write = (data: Uint8Array | number[]) =>
  invoke("pty_write", { data: Array.from(data) });

term.onData((data) => write(encoder.encode(data)));

// macOS expects Cmd, Folio speaks Ctrl.
//
// Translate one to the other rather than teaching Folio a second set of
// bindings: the deck build and this build stay one codebase, and a
// student moving between them presses the key their machine taught them.
//
// The exclusions are the keys macOS itself owns. Cut/copy/paste/select-all
// stay with the Edit menu, and hide/quit with the app menu; intercepting
// those would break the shortcuts every other Mac app has trained into
// the user. Everything else -- s, b, i, z, y, f, o, n, r, p, g, w --
// reaches Folio as the control code it already understands.
const SYSTEM_OWNED = new Set(["c", "v", "x", "a", "q", "h"]);
const isMac = navigator.platform.toLowerCase().includes("mac");

term.attachCustomKeyEventHandler((e) => {
  if (!isMac || !e.metaKey || e.ctrlKey || e.altKey) return true;
  if (e.type !== "keydown") return true;

  const key = e.key.toLowerCase();

  // Font size is the wrapper's to own: xterm.js decides the cell size, so
  // Folio's own font setting (which edits the deck's foot.ini) cannot
  // reach it. Cmd +/-/0 is what a Mac user will try.
  if (key === "=" || key === "+" || key === "-" || key === "_" || key === "0") {
    const cur = term.options.fontSize ?? FONT_SIZE;
    let next = cur;
    if (key === "0") {
      next = 15;
    } else {
      const dir = key === "-" || key === "_" ? -1 : 1;
      const at = FONT_STEPS.indexOf(cur);
      const idx = at === -1 ? FONT_STEPS.indexOf(15) : at;
      next = FONT_STEPS[Math.min(Math.max(idx + dir, 0), FONT_STEPS.length - 1)];
    }
    if (next !== cur) {
      term.options.fontSize = next;
      localStorage.setItem("folio.fontSize", String(next));
      fit.fit();
      invoke("pty_resize", { cols: term.cols, rows: term.rows });
    }
    e.preventDefault();
    return false;
  }

  // Cmd+Up / Cmd+Down are the Mac idiom for document start and end, which
  // Folio binds to Ctrl+Up / Ctrl+Down.
  if (key === "arrowup" || key === "arrowdown") {
    write(encoder.encode(key === "arrowup" ? "\x1b[1;5A" : "\x1b[1;5B"));
    e.preventDefault();
    return false;
  }

  if (key.length !== 1 || key < "a" || key > "z") return true;
  if (SYSTEM_OWNED.has(key)) return true;

  write([key.charCodeAt(0) - 96]); // 'a' -> 0x01
  e.preventDefault();
  return false;
});

// Drop the frame in full screen.
//
// The matte exists to make a floating window read as a border around the
// page. Full screen has no window to border, and the display's own corner
// radius is far larger than any inner radius we could pick -- an inset
// page with a tight corner sits visibly wrong inside that much bigger
// curve. Filling the display instead lets its corners do the rounding,
// and hands the extra room to the writing, which is the point.
//
// Measured from the window's own geometry rather than asked of macOS.
// The full-screen style mask is set at different points going in and
// coming out, so querying it is both racy -- it needed late re-checks to
// come back reliably -- and late: the frame changed after the OS
// animation had finished, as a separate visible stage. The size is true
// synchronously and moves in step with what is actually on screen, so the
// matte now goes as the window reaches the display and returns the moment
// it leaves, inside the animation rather than after it.
const isFullscreen = () =>
  window.innerWidth >= screen.width && window.innerHeight >= screen.height;

/** Sync the frame to the window geometry. True if it actually changed. */
function syncFrame(): boolean {
  const full = isFullscreen();
  if (document.body.classList.contains("fullscreen") === full) return false;
  document.body.classList.toggle("fullscreen", full);
  return true;
}

// The size the pty was last told about. `fit` already declines to resize
// the grid when the cell count has not changed, but the pty call did not:
// it sent a SIGWINCH for every stray resize event, and Folio repaints its
// whole screen on each one. During a full-screen animation that is a
// stream of identical resizes and a stream of full repaints -- flicker
// with nothing behind it.
let sentCols = 0;
let sentRows = 0;

const refit = () => {
  fit.fit();
  if (term.cols === sentCols && term.rows === sentRows) return;
  sentCols = term.cols;
  sentRows = term.rows;
  // Swallowed deliberately: a frame change can land before pty_start has
  // finished, and "pty not started" is the right answer then -- the size
  // it would have set is the one start() is about to use.
  invoke("pty_resize", { cols: term.cols, rows: term.rows }).catch(() => {});
};

// Resize has to reach the pty, not just the renderer: Folio reads the
// terminal size at runtime to choose its chrome.
let resizeTimer: number | undefined;
let lastRefit = 0;

window.addEventListener("resize", () => {
  // Every event: it is a class toggle and nothing more.
  syncFrame();

  // Re-measuring only when the size stops moving makes the whole grid
  // jump once at the end, which is the "staged" part. Re-measuring on
  // every event instead would ask a Python TUI to repaint its entire
  // screen through a pty at animation frame rate, which it cannot do --
  // the backlog would outlast the animation.
  //
  // So: throttled. A few intermediate steps track the window during the
  // transition, and a final fit lands the exact size once it settles.
  // Steps that change nothing cost nothing -- refit returns early when
  // the cell count is unmoved.
  const now = performance.now();
  if (now - lastRefit > 100) {
    lastRefit = now;
    refit();
  }
  clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    lastRefit = performance.now();
    refit();
  }, 120);
});


// Folio's exit codes, from run.sh -- the launcher loop the deck runs it
// under. 43 asks for a plain relaunch, which is how changing the vault
// root rebinds everything cleanly; 42 asks for pull-then-relaunch, which
// a frozen build cannot do (updates arrive as a new build), so it is
// treated the same. In the wrapper there is no launcher loop, so this is
// it -- without one, changing the vault exits Folio and leaves the window
// showing a dead terminal and nothing else.
const RELAUNCH_CODES = new Set([42, 43]);

// A relaunch is a user action -- changing the vault root -- so it should
// never repeat quickly. If it does, something is asking to restart on
// startup and looping would peg a core and explain nothing.
let relaunches: number[] = [];

const exited = new Channel<number>();
exited.onmessage = (code) => {
  if (RELAUNCH_CODES.has(code)) {
    const now = Date.now();
    relaunches = relaunches.filter((t) => now - t < 10_000);
    relaunches.push(now);
    if (relaunches.length > 3) {
      term.write(
        "\r\n\x1b[31mFolio keeps asking to restart.\x1b[0m " +
          "Stopping, rather than looping.\r\n",
      );
      return;
    }
    void launch();
    return;
  }
  // Any other exit is the user quitting, or a crash. Say so: scrollback
  // is disabled, so a traceback has already scrolled away, and a blank
  // window is the least useful thing we could show.
  term.write(
    `\r\n\x1b[33mFolio exited (code ${code}).\x1b[0m ` +
      `Close the window, or reopen Folio to start again.\r\n`,
  );
};

async function launch() {
  const program = await invoke<string>("folio_path");
  // Report the size we actually have. Claiming a wider terminal than the
  // window can show makes Folio lay out to columns that are not there and
  // the right-hand edge wraps into nonsense; the window's minimum size is
  // what guarantees the roomy chrome, not a number invented here.
  sentCols = term.cols;
  sentRows = term.rows;
  await invoke("pty_start", {
    program,
    args: [],
    cols: term.cols,
    rows: term.rows,
    onOutput: output,
    onExit: exited,
  });
  term.focus();
}

async function start() {
  // Measure the grid only once the real font is resident. xterm.js takes
  // its cell size from whatever face is available at open() -- if that is
  // the fallback, every column lands slightly wrong and stays wrong until
  // something forces a remeasure.
  await Promise.all([
    document.fonts.load(`${FONT_SIZE}px "JetBrains Mono"`),
    document.fonts.load(`bold ${FONT_SIZE}px "JetBrains Mono"`),
    document.fonts.load(`italic ${FONT_SIZE}px "JetBrains Mono"`),
  ]);
  await document.fonts.ready;

  term.open(document.getElementById("terminal")!);
  applyTheme();
  syncFrame();

  // The WebGL renderer, for the box-drawing characters rather than for
  // speed. Folio draws its panel dividers and dialog frames with U+2500
  // box glyphs, and the default DOM renderer takes those from the font --
  // so each cell gets a bar its own height, and with lineHeight 1.25 the
  // extra leading shows as a gap between every row. The result is a
  // dotted divider where a continuous rule belongs. This renderer honours
  // `customGlyphs` (on by default), which draws those characters to the
  // full cell instead, and joins the lines back up.
  //
  // Falling back is safe: without it the dividers segment again, which is
  // cosmetic, so a machine that cannot give us a context still runs.
  try {
    const webgl = new WebglAddon();
    webgl.onContextLoss(() => webgl.dispose());
    term.loadAddon(webgl);
  } catch {
    /* DOM renderer; dividers will segment. */
  }

  fit.fit();

  await launch();
}

// A click anywhere is a click into the document; without this the cursor
// stops responding after any window-level interaction.
window.addEventListener("mousedown", () => term.focus());

start().catch((e) => {
  term.write(`\r\n\x1b[31mFolio failed to start:\x1b[0m ${e}\r\n`);
});
