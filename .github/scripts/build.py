#!/usr/bin/env python3
"""Сборка сайта прототипов для GitHub Pages.

1. Копирует отслеживаемые git-файлы в _site (кроме служебных).
2. Вставляет <meta name="robots" content="noindex, nofollow"> во все HTML.
3. Пишет _site/history.json: история коммитов по каждому HTML-файлу
   (с учётом переименований; чистые переносы R100 пропускаются).
"""
import json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
OUT = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "_site")
HISTORY_LIMIT = 30
NOINDEX = '<meta name="robots" content="noindex, nofollow">'


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def tracked_files():
    files = [f for f in git("ls-files", "-z").split("\0") if f]
    return [f for f in files if not f.startswith(".github/") and not f.startswith(".") and "/." not in f]


def file_history(path):
    out = git("log", "--follow", "-M", "--format=%x1e%H%x1f%aI%x1f%an%x1f%s", "--name-status", "--", path)
    entries = []
    for block in out.split("\x1e"):
        block = block.strip("\n")
        if not block:
            continue
        head, _, rest = block.partition("\n")
        sha, date, author, subject = head.split("\x1f", 3)
        statuses = [l.split("\t")[0] for l in rest.splitlines() if l.strip()]
        if statuses and all(s == "R100" for s in statuses):
            continue  # перенос без изменений содержимого
        entries.append({"sha": sha, "date": date, "author": author, "message": subject})
        if len(entries) >= HISTORY_LIMIT:
            break
    return entries


def inject_noindex(html):
    if re.search(r'<meta[^>]+name=["\']robots["\']', html, re.I):
        return html
    m = re.search(r"<head[^>]*>", html, re.I)
    if m:
        return html[: m.end()] + "\n" + NOINDEX + html[m.end():]
    return NOINDEX + "\n" + html


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    files = tracked_files()
    history = {}
    for f in files:
        src, dst = os.path.join(ROOT, f), os.path.join(OUT, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if f.lower().endswith(".html"):
            with open(src, encoding="utf-8", errors="surrogateescape") as fh:
                html = fh.read()
            with open(dst, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(inject_noindex(html))
            history[f] = file_history(f)
        else:
            shutil.copy2(src, dst)
    data = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": history,
    }
    with open(os.path.join(OUT, "history.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, ".nojekyll"), "w") as fh:
        fh.write("")
    print(f"built {len(files)} files, history for {len(history)} html files -> {OUT}")


if __name__ == "__main__":
    main()
