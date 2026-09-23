// Sign the frozen Folio folder before Tauri bundles it (beforeBundleCommand).
//
// Tauri signs the app and anything it ships as an externalBin, but Folio
// ships as a resource folder, and Tauri does not look inside resources for
// code. Left alone, the executables in there keep PyInstaller's ad-hoc
// signature, the app seals them into its bundle as if they were data, and
// notarization rejects the whole thing for unsigned binaries. So each one
// is signed here with the same identity and the hardened runtime.
//
// A no-op off macOS and when APPLE_SIGNING_IDENTITY is unset, which is
// every dev build and CI: those produce unsigned apps to test, not ones to
// ship.
import { execFileSync } from "node:child_process";
import { openSync, readSync, closeSync, readdirSync, statSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const identity = process.env.APPLE_SIGNING_IDENTITY;
if (process.platform !== "darwin" || !identity) process.exit(0);

const tauriDir = join(dirname(fileURLToPath(import.meta.url)), "..", "src-tauri");
const root = join(tauriDir, "folio-dist");
const entitlements = join(tauriDir, "entitlements.plist");

// Mach-O and fat-binary magic numbers, in both byte orders.
const MAGIC = new Set([0xfeedface, 0xfeedfacf, 0xcefaedfe, 0xcffaedfe, 0xcafebabe, 0xbebafeca]);

function isMachO(path) {
  const fd = openSync(path, "r");
  try {
    const buf = Buffer.alloc(4);
    return readSync(fd, buf, 0, 4, 0) === 4 && MAGIC.has(buf.readUInt32BE(0));
  } finally {
    closeSync(fd);
  }
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (st.isFile() && isMachO(p)) out.push(p);
  }
  return out;
}

const main = join(root, "folio");
const code = walk(root);
if (!code.includes(main)) {
  console.error(`sign-folio: ${main} not found -- run ./freeze.sh first.`);
  process.exit(1);
}

// Libraries and helpers first, the executable that loads them last.
const ordered = [...code.filter((p) => p !== main), main];
for (const path of ordered) {
  const args = ["--force", "--sign", identity, "--options", "runtime", "--timestamp"];
  if (path === main) args.push("--entitlements", entitlements);
  execFileSync("codesign", [...args, path], { stdio: "inherit" });
  console.log(`sign-folio: signed ${path.slice(root.length + 1)}`);
}
console.log(`sign-folio: ${ordered.length} binaries in ${basename(root)}/ signed`);
