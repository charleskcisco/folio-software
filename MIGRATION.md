# Moving a deck from Journal to Folio

Folio is the same software under a new name. The vault is untouched, and
settings carry over on their own. The work is repointing the device at the
new repository.

Budget ten minutes, and do it when you are not relying on the deck.

## Before you start: write down your rotation

`device-setup.sh` **overwrites `~/start-deck.sh`** from a template. That
file holds the screen rotation, and the template's default is *no
rotation* — so a rotated deck comes back landscape and looks broken.

Read the values first:

```
grep DECK_ROTATE ~/start-deck.sh
```

Keep whatever it prints. On a typical writerdeck it is something like
`DECK_ROTATE_OUTPUT="HDMI-A-1"` and `DECK_ROTATE_TRANSFORM="90"`.

## 1. Clone Folio beside the old checkout

Do not delete the Journal directory yet. It costs nothing to keep and it
is the fastest way back if something is wrong.

```
cd ~
git clone https://github.com/charleskcisco/folio-software.git
```

## 2. Install dependencies

```
cd ~/folio-software && ./setup.sh
```

`setup.sh` installs only the Python side: a virtual environment with
prompt_toolkit and pygments. It does **not** install pandoc, LibreOffice,
aspell or typst — those came from `app-setup.sh` when the deck was first
built, and they are still there. Migrating repoints the launcher; it does
not rebuild the machine.

If `setup.sh` warns that typst is missing, that is expected on a deck that
never had it, and nothing is broken: see the note on export engines below.

## 3. Point the device at it

```
./device-setup.sh
```

This rewrites `~/start-deck.sh` to launch from `~/folio-software`,
installs the foot terminal config, and adds the TTY1 auto-launch to
`~/.bashrc` if it is not already there (it is guarded by a marker, so
re-running is safe).

## 4. Put the rotation back

This is the step people forget, and the symptom — a sideways screen — does
not look like a missed step.

```
nano ~/start-deck.sh
```

Set `DECK_ROTATE_OUTPUT` and `DECK_ROTATE_TRANSFORM` to the values from
before. Or, in one line:

```
sed -i 's|^DECK_ROTATE_OUTPUT=.*|DECK_ROTATE_OUTPUT="${DECK_ROTATE_OUTPUT:-HDMI-A-1}"|' ~/start-deck.sh
```

## 5. Reboot

```
sudo reboot
```

## What happens on first launch

Your config moves itself. `~/.config/journal/config.json` is copied to
`~/.config/folio/config.json`, so the vault path, colour scheme, pinned
entries and export engine all survive. If the copy fails for any reason
the old file is still read, so the worst case is that it tries again next
time rather than losing anything.

`JOURNAL_*` environment variables still work. `FOLIO_*` wins where both
are set, so there is no rush to change them.

**Your writing is not touched.** The vault is a directory named in the
config; nothing in this process moves or rewrites it.

## Your export engine does not change

A migrated deck keeps exporting through **LibreOffice**, deliberately.
Folio treats an existing config as a device that has been exporting that
way since before the setting existed, and does not switch it -- silently
changing the export engine of a working device is how one stops working,
possibly in someone else's hands.

So typst is not required to migrate. It is only needed if you then pick it
yourself in Options, and if it is missing there:

```
cd ~/folio-software && ./install-typst.sh
```

Fresh installs start on typst; migrated ones do not. That is the intended
difference, not an oversight.

## Checking it worked

- The top-left says **Folio**
- Your entries are listed, with their real modification dates
- The screen is the right way up
- Options shows your vault path, unchanged

## If something is wrong

The old checkout is still there. Point `~/start-deck.sh` back at it and
reboot:

```
sed -i 's|/home/[^/]*/folio-software|/home/'"$USER"'/journal|g' ~/start-deck.sh
sudo reboot
```

Then say what happened, because it means this document is missing a step.
