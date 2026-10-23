"""Пересборка файлов оверлея и манифеста под новую версию.

Пример:
  python tools/build.py --upstream ../work/upstream-0.3.9 \
                        --ru ../work/ru-0.3.9 --version 0.3.9

Обновляет files/ и manifest.json. renames.json правится руками (новые
ассеты апстрима надо перевести и добавить туда же). Скрипт предупреждает
о новых/пропавших ассетах и о файлах, где остался китайский текст.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")
ROOT = Path(__file__).resolve().parent.parent

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


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, help="распакованный package/ новой версии")
    ap.add_argument("--ru", required=True, help="переведённое дерево (вывод tools/update.py)")
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    up, ru = Path(args.upstream), Path(args.ru)

    renames_path = ROOT / "renames.json"
    renames = json.loads(renames_path.read_text(encoding="utf-8"))
    gone = [r["from"] for r in renames if not (up / r["from"]).exists()]
    if gone:
        print(f"! исчезли ассеты ({len(gone)}): {gone[:5]}")
    known = {r["from"] for r in renames}
    fresh = []
    for sub in ("assets/webm", "assets/memes", "assets/fonts", "assets/pic"):
        d = up / sub
        if d.is_dir():
            for p in d.iterdir():
                rel = f"{sub}/{p.name}"
                if rel not in known and CJK.search(p.name):
                    fresh.append(rel)
    if fresh:
        print(f"! новые ассеты без перевода ({len(fresh)}): допишите их в renames.json")
        for f in fresh[:10]:
            print("   ", f)

    out = ROOT / "files"
    if out.exists():
        shutil.rmtree(out)
    entries = []
    for rel in FILES:
        a, b = up / rel, ru / rel
        if not b.exists():
            sys.exit(f"нет переведённого файла {rel}")
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(b, dst)
        entries.append({"path": rel, "before": sha(a), "after": sha(b), "size": b.stat().st_size})

    manifest = {
        "name": "dsh-pet-ru",
        "upstream": {
            "name": "dsh-pet",
            "version": args.version,
            "repository": "https://github.com/PC2005-cloud/dsh-pet",
            "tarball": f"https://registry.npmjs.org/dsh-pet/-/dsh-pet-{args.version}.tgz",
        },
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "files": entries,
        "renames": len(renames),
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"готово: {len(entries)} файлов, renames={len(renames)}, версия {args.version}")


if __name__ == "__main__":
    main()
