# update_ventoy_isos

Keeps the ISOs on a [Ventoy](https://www.ventoy.net/) stick up to date. One
script, no dependencies beyond the Python standard library, runs on Windows,
Linux and macOS.

It auto-detects the newest version of every ISO in its catalog (directory
listings, SourceForge RSS, the GitHub API, the NixOS channel bucket,
massgrave.dev), downloads only what actually changed, and cleans up the
versions it replaced.

## Usage

```sh
python update_ventoy_isos.py                 # interactive: pick drive, then ISOs
python update_ventoy_isos.py --dest E:\      # explicit target
python update_ventoy_isos.py --dry-run       # report only, write nothing
python update_ventoy_isos.py --force         # ignore the manifest, redownload
```

Without `--dest` the script lists the removable drives it found and lets you
choose one, so there is no drive letter to type. Detection uses the Win32 drive
type on Windows, the removable flag under `/sys` on Linux, and `/Volumes` on
macOS.

It also works under WSL, where the stick is a drvfs mount with no block device
behind it: there the script asks Windows which drive is removable. If that WSL
setup has `.exe` interop disabled -- common on Arch images booting systemd,
where `systemd-binfmt` drops the `WSLInterop` registration -- it falls back to
the drvfs mounts under `/mnt/`, leaving out the system drive, and labels them
as unverified. WSL only automounts drives that existed when it started, so a
stick plugged in later needs mounting first; the picker prints the exact
command when it sees one.

## What it does

**Updates Ventoy itself first.** Before touching a single ISO, the script
compares the newest Ventoy release against what it last installed and offers to
update (default yes; `--no-ventoy` skips the check). The update is handed to
Ventoy's own installer rather than reimplemented -- it rewrites a bootloader,
and there is one correct way to do that.

Ventoy keeps its version on the VTOYEFI partition, which needs raw device
access to read, so the installed version is only known once this script has
installed it; before that it says so. The offer appears only for the root of a
removable drive that carries a `ventoy` directory, so `--dest C:\isos` can never
put a bootloader rewrite one keystroke away. From WSL it is declined outright --
no raw access to the USB device.

**Only downloads what changed.** Every downloaded ISO is recorded in
`ventoy_versions.json` next to the ISOs. On the next run the newest version
online is compared against that record; rolling releases that keep the same
filename are checked via the remote size / `Last-Modified` header. ISOs that
were already on the stick are adopted instead of re-downloaded -- including the
case where a download finished but was never recorded, which otherwise cost a
full re-fetch of several GB.

**Verifies what it downloads.** Where the source publishes a checksum -- a
`SHA256SUMS` for the directory, or a per-image `.sha256` / `.DIGESTS` -- the
finished file is hashed and compared before it is put in place, so a corrupted
or tampered image never reaches the stick. Roughly half of the catalog
publishes one; the rest falls back to the size check, and each download says
which of the two it got. `--no-verify` turns it off.

**Shows what it would do.** `--dry-run` runs the whole detection pass, prints
what would be downloaded, skipped or deleted, and writes nothing at all -- no
ISOs, no manifest, not even the target folder.

**Shows you what is on the stick** before you pick anything -- item, exact
filename, size -- and marks those entries in the picker, so nothing gets
selected twice. If the stick already holds something, the menu offers
*"Update what's there"*: start from the current set and just refresh it.

**Removes superseded versions.** After the downloads it finds ISOs that a newer
release replaced -- including ones the manifest never knew about -- lists each
one next to the file that superseded it, and deletes them once you confirm
(`--cleanup ask|yes|no`).

**~60 items in the catalog**, grouped by family: desktop distros, the official
Ubuntu flavours, server/enterprise (including the Proxmox products and XCP-ng),
security, rescue tools, BSD. Pick a preset
(Standard / Advanced / Everything) or individual numbers and ranges like
`1,3,5-9`, `+12`, `-4`.

**Downloads with resume support** (HTTP Range), showing the serving host and
live speed in MB/s and Mbit/s. Where a machine-readable mirror list exists
(currently Arch), the best-scored mirrors are briefly speed-tested and the
fastest one is used -- disable with `--no-mirror-test`.

**Windows ISOs** are in no preset, because none of the three ways to get them
runs unattended. Pick them and the script asks which method to use, spelling out
what each one costs; pass `--windows` to skip that prompt.

| Method | What it does | Upside | Downside |
| --- | --- | --- | --- |
| `massgrave` *(default)* | opens the massgrave.dev page, says which entry to click, then watches your Downloads folder and files the ISO onto the stick | always works, no admin | you click the download yourself |
| `uup` | pulls the build from Windows Update and assembles the ISO locally with DISM | official and unattended | Windows only, needs admin, ~40 min and ~15 GB free |
| `fido` | resolves an official direct Microsoft download link | light, no admin, no browser | Windows only, blocked unpredictably by Microsoft's anti-bot "Sentinel" |

## Options

| Flag | Effect |
| --- | --- |
| `--dest PATH` | target folder / Ventoy drive (omit for the interactive picker) |
| `--dry-run` | report what would change; write nothing |
| `--force` | re-download everything, ignoring the manifest |
| `--no-verify` | skip the SHA-256 check |
| `--no-ventoy` | skip the Ventoy self-update check |
| `--version` | print the version and exit |
| `--preset standard\|advanced\|everything\|custom` | skip the menu |
| `--cleanup ask\|yes\|no` | what to do with superseded ISOs (default `ask`) |
| `--no-mirror-test` | skip the fastest-mirror speed test |
| `--windows massgrave\|fido\|uup` | how to obtain the Windows ISOs |

## Requirements

Python 3.6+. Nothing else -- standard library only.

## Development

The catalog resolves download URLs from ~50 foreign directory listings, so the
usual way this breaks is an upstream reorganizing its mirror. `check_resolvers`
asks every upstream whether its resolver still finds an ISO:

```sh
python tests/check_resolvers.py
```

It also pins one invariant that already bit once: openSUSE Leap must resolve to
the newest release on the mirror. Leap 16 moved its installer to a new path and
filename, the resolver stopped matching, and instead of failing it quietly kept
serving end-of-life 15.6 -- so "the resolver returned something" is not enough
on its own.

Failures are retried once before the check gives up, because a mirror that
times out under parallel requests is a hiccup, not a broken layout. GitHub
Actions runs the whole thing every Monday.

## License

MIT -- see [LICENSE](LICENSE).
