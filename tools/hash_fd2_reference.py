#!/usr/bin/env python3
"""計算本專案反向工程所依據之原版檔案版本指紋。

只讀取玩家自備的合法原版檔案，不複製內容。預設輸出穩定排序的 JSON，
可與 docs/data/fd2-reference-files.json 比對。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REFERENCE_FILES = (
    "FD2.EXE",
    "ANI.DAT",
    "BG.DAT",
    "DATO.DAT",
    "FDFIELD.DAT",
    "FDICON.B24",
    "FDMUS.DAT",
    "FDOTHER.DAT",
    "FDSHAP.DAT",
    "FDTXT.DAT",
    "FIGANI.DAT",
    "TAI.DAT",
    "TITLE.DAT",
)


def digest(path: Path) -> dict[str, object]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return {
        "file": path.name,
        "size": size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_dir", type=Path, help="含 FD2.EXE 的原版 FLAME2 目錄")
    args = parser.parse_args()

    missing = [name for name in REFERENCE_FILES if not (args.game_dir / name).is_file()]
    if missing:
        parser.error("缺少原版檔案：" + "、".join(missing))

    result = {
        "schema_version": 1,
        "scope": "FD2 反向工程所使用的執行檔與唯讀遊戲資產；不含可變動的 FD2.SAV、FD2.TMP",
        "files": [digest(args.game_dir / name) for name in REFERENCE_FILES],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
