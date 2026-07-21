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
python update_ventoy_isos.py --force         # ignore the manifest, redownload
```

Without `--dest` the script lists the removable drives it found and lets you
choose one, so there is no drive letter to type.

## What it does

**Only downloads what changed.** Every downloaded ISO is recorded in
`ventoy_versions.json` next to the ISOs. On the next run the newest version
online is compared against that record; rolling releases that keep the same
filename are checked via the remote size / `Last-Modified` header. ISOs that
were already on the stick are adopted instead of re-downloaded.

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

**Windows ISOs** are not part of any preset because they cannot be fetched
unattended. The default (`--windows massgrave`) opens the massgrave.dev pages,
tells you which entry to pick, then watches the stick and your Downloads
folder: whatever ISO you download is matched, renamed to the canonical name and
moved onto the stick automatically. Two automatic alternatives exist:
`--windows fido` resolves an official direct Microsoft link (light, no admin,
but subject to Microsoft's anti-bot "Sentinel"), `--windows uup` pulls the build
from Windows Update and assembles the ISO locally (no bot protection, but needs
administrator rights, ~40 minutes and ~15 GB of scratch space).

## Options

| Flag | Effect |
| --- | --- |
| `--dest PATH` | target folder / Ventoy drive (omit for the interactive picker) |
| `--force` | re-download everything, ignoring the manifest |
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
