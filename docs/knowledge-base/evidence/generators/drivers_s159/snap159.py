# 存檔:原 scratchpad 驅動腳本(續一百五十九),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十九第 6 項:把磁碟上三份 FD2 目錄(GAME/FD2、FD2_USB、FD2_APK)的檔名、大小、修改時間、md5 存成快照,
並把 FD2_APK 裡 1995-07-15 的三個小檔(PASS.DAT、PLAY.BAT、SETUP.BAT)複製到 .wsl_build/s159_copyprot/。只讀來源,不改任何遊戲檔。"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
from pathlib import Path

GAME = Path(r"C:/Users/kg701/Desktop/GAME")
OD = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/s159_copyprot")
OD.mkdir(parents=True, exist_ok=True)
snap: dict[str, list[dict]] = {}
for sub in ("FD2", "FD2_USB", "FD2_APK"):
    rows = []
    for p in sorted((GAME / sub).iterdir()):
        if not p.is_file():
            continue
        st = p.stat()
        if datetime.datetime.fromtimestamp(st.st_mtime).year >= 2010 and p.suffix.upper() != ".EXE":
            continue  # 2010 之後的是這個專案自己放的分析檔,不是發行物
        rows.append({"name": p.name, "size": st.st_size,
                     "mtime_local": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                     "md5": hashlib.md5(p.read_bytes()).hexdigest()})
    snap[sub] = rows
snap["_note"] = "快照時間 " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + ";mtime 為 Windows 本地時間(UTC+8)"
(OD / "dirs.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
for n in ("PASS.DAT", "PLAY.BAT", "SETUP.BAT"):
    shutil.copy2(GAME / "FD2_APK" / n, OD / n)
print({k: len(v) for k, v in snap.items() if k != "_note"})
