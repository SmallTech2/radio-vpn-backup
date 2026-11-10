#!/usr/bin/env python3
"""Une archive par jour/semaine UTC ; ne touche a aucun autre fichier."""
import datetime as dt
import pathlib
import re
import sys


def retained(names, daily=7, weekly=4):
    days, weeks = {}, {}
    for name in sorted(names, reverse=True):
        stamp = dt.datetime.strptime(name[:16], "%Y%m%dT%H%M%SZ")
        days.setdefault(stamp.date(), name)
        weeks.setdefault(stamp.isocalendar()[:2], name)
    return set(list(days.values())[:daily]) | set(list(weeks.values())[:weekly])


def prune(folder, daily, weekly):
    if daily < 1 or weekly < 1:
        raise ValueError("Retentions positives requises.")
    files = {p.name: p for p in folder.iterdir() if re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\.tar\.gz(?:\.age)?", p.name)
             and p.is_file() and not p.is_symlink()}
    keep = retained(files, daily, weekly)
    for name in files.keys() - keep:
        files[name].unlink()
        files[name].with_name(name + ".sha256").unlink(missing_ok=True)


if __name__ == "__main__":
    prune(pathlib.Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
