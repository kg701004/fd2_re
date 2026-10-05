# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十三 v11 的額外設定(在 v9_setup 之後跑)。用法:python v11_setup.py <inst> <out_dir>

- 索爾(單位 0)的 +7 由 32 改成 20:亂碼畫面的頭像若來自「索爾行動後 0x1967e 依單位 +7 載入」,會跟著變成 20(v9b 來源的翻轉對照)。
- 名冊尾端加 3 筆(複製第 0 筆再改):
    R_a:id X、+7 = 10、座標 (5, 40)
    R_b:id X、+7 = 11、座標 (6, 41)   —— 同 id 兩筆,0x12c60 名冊掃描「最後一筆」勝出 → 預測 11、(6, 41)
    R_c:id Z、+7 = 12、座標 (7, 42)   —— 戰場上會有一個 id Z 的「死亡」單位,名冊不會被掃 → 預測不用這筆
- 選出 id:X、Z、A(都不在戰場與名冊,也不是 0x27),A 給「兩邊都沒有」用。
- 選出 U(之後在 k = 1 才把它的 +8 改 Z、+5 設 bit0、+7 改 13)。
結果寫進 <out_dir>/v11_plan.json。
"""
from __future__ import annotations

import json
import struct
import sys

from live import DELTA, ROOT, Live

inst, out = sys.argv[1], sys.argv[2]
L = Live(inst, ROOT / out)
assert L.halt(), "halt"
G = lambda a: L.d32(a + DELTA)  # noqa: E731

n = G(0x53BEB) & 0xFF
u = L.units("v11_pre_units", n)
rn, rp = G(0x53BFB), G(0x53BF7)
assert 0 < rn <= 28, rn
r = L.dump(rp, 32 * 0x50, "v11_pre_roster")
bf_ids = {u[i * 0x50 + 8] for i in range(n)}
ro_ids = {r[i * 0x50 + 8] for i in range(rn)}
cand = [i for i in range(2, 0x80) if i not in bf_ids and i not in ro_ids and i != 0x27]
X, Z, A = cand[0], cand[1], cand[2]

# U:未參與測試、已麻痺、不在 12 / 16 / 48..53 的單位,取索引最大的
U = max(i for i in range(1, n) if i not in (12, 16) and not 48 <= i <= 53 and u[i * 0x50 + 0x26] == 9
        and not u[i * 0x50 + 5] & 1)
sol7 = u[7]
L.sm(L.ua(0, 7), bytes([20]))

base = bytearray(r[0:0x50])
recs = []
for k, (cid, p7, xy) in enumerate([(X, 10, (5, 40)), (X, 11, (6, 41)), (Z, 12, (7, 42))]):
    b = bytearray(base)
    b[0], b[1], b[7], b[8] = xy[0], xy[1], p7, cid
    L.sm(rp + (rn + k) * 0x50, bytes(b))
    recs.append({"index": rn + k, "addr": hex(rp + (rn + k) * 0x50), "char_id": cid, "+7": p7, "xy": list(xy)})
L.sm(0x53BFB + DELTA, struct.pack("<I", rn + 3))

u2 = L.units("v11_post_units", n)
r2 = L.dump(rp, 32 * 0x50, "v11_post_roster")
assert u2[7] == 20, u2[7]
assert G(0x53BFB) == rn + 3
for rec in recs:
    i = rec["index"]
    assert r2[i * 0x50 + 8] == rec["char_id"] and r2[i * 0x50 + 7] == rec["+7"], rec
plan = {"units": n, "ubase": hex(L.ubase), "roster_ptr": hex(rp), "roster_count_before": rn,
        "roster_count_after": rn + 3, "X": X, "Z": Z, "A": A, "U": U,
        "U_before": {"xy": [u[U * 0x50], u[U * 0x50 + 1]], "+5": u[U * 0x50 + 5], "+7": u[U * 0x50 + 7],
                     "+8": u[U * 0x50 + 8]},
        "sol_plus7_before": sol7, "sol_plus7_after": u2[7], "roster_added": recs,
        "unit12_xy": [u[12 * 0x50], u[12 * 0x50 + 1]], "battle_ids": sorted(bf_ids), "roster_ids": sorted(ro_ids),
        "ivt_0_8": L.dump(0, 8, "v11_ivt").hex()}
(L.out / "v11_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(plan, ensure_ascii=False))
L.resume()
