#!/usr/bin/env python3
"""Smoke-test every resolver in the catalog against the live upstreams.

The script depends on ~50 foreign directory layouts. When one of them changes,
the matching resolver stops finding an ISO -- and the only way to notice is to
ask the upstreams. Run this on a schedule so a broken layout shows up here
instead of in front of the Ventoy stick.

Exit code is 1 if any resolver failed, 0 otherwise.

    python tests/check_resolvers.py
"""

import concurrent.futures as cf
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), "update_ventoy_isos.py")


def load_module():
    spec = importlib.util.spec_from_file_location("update_ventoy_isos", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve(entry):
    """Call one resolver, never raise. -> (key, label, ok, detail)"""
    key, label, fn = entry
    try:
        result = fn()
        return key, label, True, result[1]
    except Exception as exc:
        return key, label, False, "%s: %s" % (type(exc).__name__, exc)


def check_catalog(mod):
    """Every 'iso' catalog entry must resolve to a download.

    Failures are retried once, sequentially and after a pause. A mirror that
    times out under twelve parallel requests is a network hiccup, not a broken
    layout, and a check that cries wolf is a check nobody reads.
    """
    entries = [(key, label, payload)
               for key, label, _cat, _tier, kind, payload in mod.CATALOG
               if kind == "iso"]
    by_key = {key: entry for entry in entries for key in (entry[0],)}

    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(resolve, entries))

    flaky = [r[0] for r in results if not r[2]]
    if flaky:
        print("  retrying %d after a pause: %s\n" % (len(flaky), ", ".join(flaky)))
        time.sleep(5)
        retried = {key: resolve(by_key[key]) for key in flaky}
        results = [retried.get(r[0], r) for r in results]

    failed = [r for r in results if not r[2]]
    for key, label, ok, detail in sorted(results, key=lambda r: (r[2], r[0])):
        print("  %-4s %-14s %-24s %s"
              % ("ok" if ok else "FAIL", key, label, detail))
    print("\n%d of %d resolvers OK." % (len(results) - len(failed), len(results)))
    return not failed


def check_leap_is_current(mod):
    """openSUSE Leap must resolve to the newest release, not an older one.

    Leap 16 moved its installer to a new path and filename scheme. The old
    resolver did not match it, silently fell through to 15.6 and kept handing
    out an end-of-life release -- a passing resolver that returns the wrong
    answer. This pins the invariant that broke: whatever the newest release
    directory on the mirror is, the resolved filename must carry that version.
    """
    try:
        newest = mod.leap_versions()[0]
        _url, name = mod.r_opensuse_leap()
    except Exception as exc:
        print("  FAIL leap           %s: %s" % (type(exc).__name__, exc))
        return False

    found = re.search(r"(\d+\.\d+)", name)
    if found and found.group(1) == newest:
        print("  ok   leap           newest release %s -> %s" % (newest, name))
        return True
    print("  FAIL leap           newest release is %s but resolved %s -- the "
          "layout for %s probably changed" % (newest, name, newest))
    return False


def check_catalog_integrity(mod):
    """Every entry needs a unique key and a description line for the picker."""
    keys = [entry[0] for entry in mod.CATALOG]
    ok = True

    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        print("  FAIL duplicate catalog keys: %s" % ", ".join(duplicates))
        ok = False

    undescribed = [k for k in keys if k not in mod.DESCRIPTIONS]
    if undescribed:
        print("  FAIL no DESCRIPTIONS entry: %s" % ", ".join(undescribed))
        ok = False

    orphaned = [k for k in mod.DESCRIPTIONS if k not in keys]
    if orphaned:
        print("  FAIL DESCRIPTIONS entry for unknown key: %s" % ", ".join(orphaned))
        ok = False

    if ok:
        print("  ok   %d catalog entries, all keyed and described." % len(keys))
    return ok


def check_auto_install(mod):
    """sync_auto_install rewrites the user's ventoy.json, so pin its edges.

    The two that matter are the ones that lose data if they regress: an entry
    for a Windows build that has been replaced must be dropped rather than left
    pointing at a missing ISO, and a hand-written entry for some other image
    must survive untouched.
    """

    class Args(object):
        dry_run = False

    root = tempfile.mkdtemp(prefix="stick_")
    try:
        os.makedirs(os.path.join(root, "ventoy"))
        os.makedirs(os.path.join(root, "template", "win11"))
        open(os.path.join(root, "template", "win11", "a.xml"), "w").close()
        current = "Win_11_25H2_English_99999.9999.iso"
        open(os.path.join(root, current), "w").close()
        open(os.path.join(root, "debian.iso"), "w").close()
        with open(os.path.join(root, "ventoy", "ventoy.json"), "w") as fh:
            json.dump({
                "theme": {"file": "/theme/x.txt"},
                "auto_install": [
                    {"image": "/Win_11_25H2_English_00000.0000.iso",
                     "template": ["/template/win11/a.xml"]},
                    {"image": "/debian.iso", "template": ["/mine/preseed.cfg"]},
                ]}, fh)

        mod.sync_auto_install(root, {"win11_en": {"filename": current}}, Args())

        with open(os.path.join(root, "ventoy", "ventoy.json")) as fh:
            config = json.load(fh)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    images = [e.get("image") for e in config.get("auto_install", [])]
    problems = []
    if "/Win_11_25H2_English_00000.0000.iso" in images:
        problems.append("stale entry for a replaced build was kept")
    if "/" + current not in images:
        problems.append("no entry for the current image")
    if "/debian.iso" not in images:
        problems.append("hand-written entry was discarded")
    if "theme" not in config:
        problems.append("the rest of ventoy.json was lost")

    if problems:
        for problem in problems:
            print("  FAIL auto-install   %s" % problem)
        return False
    print("  ok   auto-install   stale dropped, current wired, foreign kept")
    return True


def main():
    mod = load_module()
    print("=== catalog integrity ===")
    integrity_ok = check_catalog_integrity(mod)
    print("\n=== catalog resolvers ===")
    catalog_ok = check_catalog(mod)
    print("\n=== version sanity ===")
    leap_ok = check_leap_is_current(mod)
    auto_ok = check_auto_install(mod)
    if integrity_ok and catalog_ok and leap_ok and auto_ok:
        return 0
    print("\nSomething upstream changed. Fix the resolver, then rerun.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
