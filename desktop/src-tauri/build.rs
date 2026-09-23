use std::path::Path;

fn main() {
    check_staged_folio();
    tauri_build::build()
}

/// Refuse to build an app around a Folio for another architecture.
///
/// freeze.sh stages the frozen folder in folio-dist/ and records what it
/// holds in folio-dist/TRIPLE. Without this check the mismatch is silent:
/// an Intel Folio inside an Apple Silicon app runs, under Rosetta, slowly,
/// and an Apple Silicon Folio inside an Intel app fails on every student
/// machine it reaches while working perfectly on the one that built it.
fn check_staged_folio() {
    let marker = Path::new("folio-dist").join("TRIPLE");
    println!("cargo:rerun-if-changed={}", marker.display());

    let target = std::env::var("TARGET").unwrap_or_default();
    let staged = match std::fs::read_to_string(&marker) {
        Ok(s) => s.trim().to_string(),
        Err(_) => panic!(
            "\n\nNo frozen Folio staged ({} is missing).\n\
             Run ./freeze.sh from the repository root first.\n\n",
            marker.display()
        ),
    };

    let matches = staged == target
        || (staged == "universal-apple-darwin" && target.ends_with("-apple-darwin"));
    if !matches {
        panic!(
            "\n\nThe staged Folio is for {staged}, but this build targets {target}.\n\
             Re-run ./freeze.sh with an interpreter for {target} (see\n\
             desktop/README.md for the Intel route), then build again.\n\n"
        );
    }
}
