"""ev_s169.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s169.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 寫盤位置與落後
    ("區塊 8 KiB", "BLOCK = 4096", "BLOCK = 8192"),
    ("漏掉 periodic 的 fflush", "    flush += [m.end() for m in re.finditer(rb\"^T periodic", "    flush += [] or [m.end() for m in re.finditer(rb\"^T periodicX"),
    ("seq 每 512 筆 fflush", "if int(m.group(1)) % 1024 == 0]", "if int(m.group(1)) % 512 == 0]"),
    ("檔尾區間擺在讀數那一行之前", "    return e0 < nxt <= e1", "    return e0 - (e1 - e0) < nxt <= e0"),
    ("對照取讀數附近", "a = _pat.search(raw, len(raw) * i // (NULL_PER_LOG + 1)).end()",
     "a = _pat.search(raw, max(0, READS[0][3] - 40 * i)).end()"),
    ("落後上界少算一塊", "    nxt = min([b + BLOCK] + [f for f in flush if f > b])", "    nxt = min([b] + [f for f in flush if f > b])"),
    ("落後取讀數之前的 t", "    LAG[f\"{tag}:{nm}\"] = round(t_at(raw, nxt - 1) - t, 2)", "    LAG[f\"{tag}:{nm}\"] = round(t_at(raw, e0 - 400) - t, 2)"),
    ("餘裕用 LEAD 加落後", "MARGIN_MS = round(LEAD_MS_S167 - LAG_MAX, 2)", "MARGIN_MS = round(LEAD_MS_S167 + LAG_MAX, 2)"),
    ("續一百六十八的說法成立", "assert S168_CLAIM_S == 1.92 and LAG_MAX < S168_CLAIM_S * 1000 / 40",
     "assert S168_CLAIM_S == 1.92 and LAG_MAX > S168_CLAIM_S * 1000 / 40"),
    # (B) HUD 邊框樣板
    ("標記檔多讀一行", "    if ln and not ln.startswith(\"#\"):", "    if ln:"),
    ("自己數吻合時右側不位移", "mine = {s: sum(px[x + (0 if s == \"L\" else 474), y] == c", "mine = {s: sum(px[x, y] == c"),
    ("樣板常數性只看左側", "        dx = 0 if lab == \"L\" else 474\n", "        dx = 0\n"),
    ("其他側別把有框那側也算進去", "OFF = [v for r in ROWS for s, v in r[\"match\"].items() if s != r[\"label\"]]",
     "OFF = [v for r in ROWS for s, v in r[\"match\"].items()]"),
    ("只用樣板的門檻 0.3", "\"frame_only\": confusion(lambda r: max(r[\"match\"].values()) >= sw.BATTLE_HUD_FRAME_MATCH_MIN)",
     "\"frame_only\": confusion(lambda r: max(r[\"match\"].values()) >= 0.3)"),
    ("舊判準只看左側", "    if sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION_R, sw.BATTLE_HUD_LEFT_STRIP_REGION_R):\n        return \"R\"\n    return None",
     "    return None"),
    ("側別比對用舊判準", "SIDE = {\"new_correct\": sum(r[\"new\"] == r[\"label\"]", "SIDE = {\"new_correct\": sum(r[\"old\"] == r[\"label\"]"),
    # (C) 實機 lc169a
    ("預測檔原文改過", "\"差 ≤ 2000 ms\", \"平均 HSV 飽和度 ≤ 110\"", "\"差 ≤ 2000 ms\", \"平均 HSV 飽和度 ≤ 111\""),
    ("標記不含狀態卡", "    if e in (LOOP, SELECT, STATUS_CARD):", "    if e in (LOOP, SELECT):\n        pass\n    if e in (LOOP, STATUS_CARD):"),
    ("送鍵時刻換算方向反了", "T_PRESS = round(T_AFTER - (H_AFTER - REP[\"t_host_press\"]) * 1000, 1)",
     "T_PRESS = round(T_AFTER + (H_AFTER - REP[\"t_host_press\"]) * 1000, 1)"),
    ("S4 門檻 111", "\"S4_sat_le_110\": \"PASS\" if SAT[\"sel_up\"] <= 110 else \"FAIL\"",
     "\"S4_sat_le_110\": \"PASS\" if SAT[\"sel_up\"] <= 111 else \"FAIL\""),
    ("S5 方向反了", "\"S5_no_hud_before_replica\": \"PASS\" if not REP[\"pre_frame_hud\"] else \"FAIL\"",
     "\"S5_no_hud_before_replica\": \"PASS\" if REP[\"pre_frame_hud\"] else \"FAIL\""),
    ("S1 不比送鍵時刻", "\"PASS\" if MKN.get(\"E 0x17aed\", 0) == 0 and T_SEL > T_PRESS else \"FAIL\"",
     "\"PASS\" if MKN.get(\"E 0x17aed\", 0) == 0 and T_SEL > T_LOOP - 1e6 and T_SEL < T_PRESS else \"FAIL\""),
    ("飽和度取整張", "convert(\"HSV\").crop((360, 215, 824, 520))).mean[1]", "convert(\"HSV\")).mean[1]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s169", MUTANTS))
