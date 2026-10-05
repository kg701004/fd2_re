"""0x14b78 落點選擇的動態驗證:離線重算彙整成證據 JSON、登錄表更新(doc98 續六十二)。先跑 sl_analyze.py r1/tie --json。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import glob
import json
import subprocess
import tempfile
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
D = ROOT / ".wsl_build" / "ctr" / "sl"
S = GEN_DIR
_TMP = tempfile.TemporaryDirectory()  # sl_analyze 的 --json 輸出寫到暫存目錄(原本寫進 .wsl_build/ctr/sl/)
EVI = out_path("move_landing_select_20260930.json")
W, H = 27, 21

calls = {}
for tag in ("r1", "tie"):
    j = Path(_TMP.name) / f"analyze_{tag}.json"
    r = subprocess.run([sys.executable, "-X", "utf8", str(S / "sl_analyze.py"), tag, "--json", str(j)], capture_output=True, text=True)
    assert r.returncode == 0 and "ALL OK" in r.stdout, r.stdout
    calls[tag] = json.loads(j.read_text(encoding="utf-8"))


def mk(f: str) -> dict:
    b = Path(f).read_bytes()
    return {(x, y): b[7 + 4 * (y * W + x)] for y in range(H) for x in range(W)}


# 0x146d1:同一次呼叫有泛洪後地圖(0x14ccf)與 0x146d1 後地圖(0x14d95)時,差集必須正好是「同陣營、+5 bit0 未設、不是自己」單位所在的可達格
block_checks = []
for tag in ("r1", "tie"):
    fs = sorted(glob.glob(str(D / f"{tag}_*")))
    us = unit = a2 = flood = None
    for f in fs:
        if f.endswith("B78.units.bin"):
            us = Path(f).read_bytes()
            st = Path(f.replace("units", "stack")).read_bytes()
            unit, a2, flood = st[0xC], st[0x10], None
        elif f.endswith("CCF.map.bin"):
            flood = mk(f)
        elif f.endswith("D95.map.bin") and flood is not None:
            land = mk(f)
            removed = sorted(c for c in flood if flood[c] != 0xFF and land[c] == 0xFF)
            added = sorted(c for c in flood if flood[c] == 0xFF and land[c] != 0xFF)
            pred = sorted({(us[i * 80], us[i * 80 + 1]) for i in range(len(us) // 80) if i != unit and not us[i * 80 + 5] & 1
                           and (us[i * 80 + 6] == 0) == (a2 == 0) and flood[(us[i * 80], us[i * 80 + 1])] != 0xFF})
            assert removed == pred and not added, (tag, unit, removed, pred, added)
            block_checks.append({"run": tag, "unit": unit, "a2": a2, "cells_removed": [list(c) for c in removed]})
assert sum(1 for b in block_checks if b["cells_removed"]) == 4, block_checks

# 平手場景:#13 那次呼叫
tie = [c for c in calls["tie"] if c["args"][2] == 13]
assert len(tie) == 1
t = tie[0]
fellow = [[24, 18], [24, 17], [23, 18], [25, 18], [24, 19]]
assert t["mode0"] == 4 and t["t_prime_at_select"] == [24, 18] and t["chosen_live"] == [23, 17]
assert not [c for c in t["list_live"] if list(c) in fellow]
last_full_tie = [25, 17]  # 同分(距離 2、abs 差 0)的另一格;「同分取最後一個」會選它
assert [23, 17] in [list(c) for c in t["list_live"]] and last_full_tie in [list(c) for c in t["list_live"]]
assert t["chosen_rival_first"] == [24, 16]

# R1 重播:#13 (1,1)->(1,7)
r = [c for c in calls["r1"] if c["args"][2] == 13][0]
assert r["dirs"] == [1, 0, 0, 0, 0, 0, 0, 3] and r["t_prime_live"] == [0, 4] and r["chosen_live"] == [0, 4]

for c in calls["r1"] + calls["tie"]:
    c["list_live"] = [list(p) for p in c["list_live"]]
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點與記憶體傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。0x14b78 內 9 個停點:入口(引數、單位表)、0x14c42(mode 0 結果)、"
            "0x14c85(mode 1 長度與方向陣列)、0x14ccf(泛洪後地圖)、0x14d37(T')、0x14d95(0x146d1 後地圖)、0x14da1(落點清單)、0x14e5b(最終選擇)、0x14ec4。"
            "每次呼叫離線重算三段:(a) 沿方向陣列(0=下、1=左、2=上、其他=右)取最後一個泛洪可達格為 T';(b) 落點清單 = 地圖 byte3 != 0xff 的格(y 外 x 內);"
            "(c) 曼哈頓距離 T' 最小、同距 abs(|dx|-|dy|) 嚴格較小才換、完全同分保留先出現者。r1 = 第 1 回合重播續六十 R1;tie = 第 2 回合平手場景"
            "(#13 在 (24,14),NPC #7 屍體與麻痺夥伴 #14 在 T = (24,18),麻痺夥伴 #15..#18 站四鄰)。",
    "calls": calls,
    "tie_case": {"actor": 13, "t_prime": [24, 18], "fellow_cells_not_landable": fellow, "chosen_live": [23, 17],
                 "rival_first_in_list": [24, 16], "rival_last_full_tie": last_full_tie},
    "r1_replay": {"actor": 13, "from": [1, 1], "target": [1, 7], "mv": r["mv"], "mode0": r["mode0"], "mode1_dirs": r["dirs"],
                  "t_prime": r["t_prime_live"], "chosen": r["chosen_live"]},
    "map_block_cells_of_side_checks": block_checks,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok", len(calls["r1"]) + len(calls["tie"]), "calls")
