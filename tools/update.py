"""Перенос перевода на новую версию dsh-pet.

Пример:
  python tools/update.py \
      --prev-upstream ../work/upstream-0.3.8 \
      --prev-ru       ../work/ru-0.3.8 \
      --new-upstream  ../work/upstream-0.3.9 \
      --out           ../work/ru-0.3.9

Скрипт извлекает пары «китайский литерал -> русский литерал» из пары
(prev-upstream, prev-ru), применяет их к new-upstream и печатает файлы,
где остались непереведённые строки. Дальше эти строки переводятся руками,
пары добавляются в перевод, и файлы пересобираются (см. README, «Обновление»).
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")

FILES = [
    "lib/client.js",
    "lib/index.js",
    "lib/standalone.js",
    "assets/config.jsonc",
    "package.json",
    "runtime/electron-helper/events.js",
    "runtime/electron-helper/index.html",
    "runtime/electron-helper/main.js",
    "runtime/electron-helper/renderer.js",
    "runtime/electron-helper/shared-core.js",
    "runtime/electron-helper/sprite.js",
]


def literals(text):
    """Границы строковых литералов в коде (комментарии пропускаются)."""
    spans, i, n = [], 0, len(text)
    state, quote, start = "code", "", 0
    while i < n:
        c = text[i]
        if state == "code":
            if c == "/" and i + 1 < n and text[i + 1] == "/":
                state, i = "line", i + 2
                continue
            if c == "/" and i + 1 < n and text[i + 1] == "*":
                state, i = "block", i + 2
                continue
            if c in "\"'":
                state, quote, start, i = "str", c, i, i + 1
                continue
            if c == "`":
                state, start, i = "tpl", i, i + 1
                continue
            i += 1
            continue
        if state == "line":
            if c == "\n":
                state = "code"
            i += 1
            continue
        if state == "block":
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                state, i = "code", i + 2
                continue
            i += 1
            continue
        if state == "str":
            if c == "\\":
                i += 2
                continue
            if c == quote:
                spans.append((start, i + 1))
                state = "code"
            i += 1
            continue
        if state == "tpl":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                spans.append((start, i + 1))
                state = "code"
            i += 1
    return spans


def read(p):
    return Path(p).read_bytes().decode("utf-8")


def extract(prev_up, prev_ru):
    pairs = []
    for rel in FILES:
        a, b = Path(prev_up, rel), Path(prev_ru, rel)
        if not a.exists() or not b.exists():
            continue
        old, new = read(a), read(b)
        lo, ln = literals(old), literals(new)
        if len(lo) != len(ln):
            print(f"  ! {rel}: число литералов разное ({len(lo)} != {len(ln)}), файл пропущен")
            continue
        for (s1, e1), (s2, e2) in zip(lo, ln):
            src, dst = old[s1:e1], new[s2:e2]
            if src != dst and CJK.search(src) and not CJK.search(dst):
                pairs.append({"file": rel, "from": src, "to": dst})
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev-upstream", required=True)
    ap.add_argument("--prev-ru", required=True)
    ap.add_argument("--new-upstream", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pairs = extract(args.prev_upstream, args.prev_ru)
    print(f"пар извлечено: {len(pairs)}")

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(args.new_upstream, out)

    by_file = {}
    for p in pairs:
        by_file.setdefault(p["file"], []).append(p)

    report, total = [], 0
    for rel in FILES:
        p = out / rel
        if not p.exists():
            continue
        text = read(p)
        hits = 0
        for pair in by_file.get(rel, []):
            n = text.count(pair["from"])
            if n:
                text = text.replace(pair["from"], pair["to"])
                hits += n
        p.write_bytes(text.encode("utf-8"))
        total += hits

        left = []
        for s, e in literals(text):
            lit = text[s:e]
            if CJK.search(lit):
                left.append(lit[:70])
        report.append({"file": rel, "hits": hits, "left": len(left), "samples": left[:8]})

    print(f"подставлено вхождений: {total}")
    for r in report:
        mark = "OK " if r["left"] == 0 else "TODO"
        print(f"  {mark} {r['file']:<44} hits={r['hits']:<4} осталось={r['left']}")
    Path("update-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("отчёт: update-report.json")


if __name__ == "__main__":
    sys.exit(main())
