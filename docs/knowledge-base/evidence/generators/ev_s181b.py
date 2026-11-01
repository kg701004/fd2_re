"""續一百八十一證據(二):evidence/mdi375_trig_s181b_20261101.json(實機 lc181a .. lc181c;預測 drivers_s181/pred181.txt)。

使用者 2026-11-01「全部依照你的建議自動進行處理」(建議:lc163a / lc167a 兩項不照字面重錄,改以觸發式擷取驗它們依賴的類別規則)。
三次都是開機 → 標題 → START → 120 秒,FD2_CALLLOG_TRIG=ng:375,ng:302-303、TRIGCAP 40,不設 SEGS / IO。
P1 每個 ng 375 區塊是 MDI 型重入夾一次 IRQ 7(0f r 0c5c:1fad、137c 段 73 條)—— 沒有 375 區塊時是 NOT TESTED。
P2 ng 302 / 303 區塊裡,從 0080:0ed6 起、回到 0x3f1a4 的那些沒有硬體中斷。
P3 分母:YC 符合 / 寫出、YN 區間總數。P4 每個區塊有 YE、trig_problems 沒有問題、寫出數 = 區塊數 ≤ 符合數。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib

from _evpaths import GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import json  # noqa: E402

OUT = out_path("mdi375_trig_s181b_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
RAW = ROOT / ".wsl_build/lc181_live"
DRV = GEN_DIR / "drivers_s181"
PRED = DRV / "pred181.txt"
# teardown 之後的指紋(lc181.py down 印出)
LOG_MD5 = {"lc181a": "0dcee91e57df141a188fb805b407d469", "lc181b": "c676d94a047c56b78e275d1e6732f17d",
           "lc181c": "b429596b086c214778fd95e39c6fe6b5"}
TRIG = "ng:375,ng:302-303"
MDI_FROM, MDI_BACK = (0x80, 0xED6), 0x3F1A4      # 續一百七十五:DOS/4GW 返回段 0080:0ed6 起、回到 int 31h 之後的 0x3f1a4
assert hashlib.md5(_EXE).hexdigest() == MD5
assert f"TRIG={TRIG}" in PRED.read_text(encoding="utf-8") and f'TRIG = "{TRIG}"' in (DRV / "lc181.py").read_text(encoding="utf-8")

RUNS = {}
for nm, m5 in LOG_MD5.items():
    p = RAW / f"{nm}_CALLLOG.TXT"
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, nm
    head = p.open(encoding="ascii").readline()
    assert head.startswith("H fd2calllog 1 ") and f" trig={TRIG} " in head and " trigcap=40" in head and " segs=" not in head, head
    lg = cs._read(str(p))
    tc = lg.trig_counts
    assert set(tc) == {0, 1} and tc[0][0] == tc[1][0] == "ng", tc
    by_rule = collections.Counter(t.rule for t in lg.trigs)
    # P4:每個區塊都讀到 YE、解析端重核沒有問題;寫出數 = 區塊數 ≤ 符合數
    assert all(t.complete for t in lg.trigs) and not [q for t in lg.trigs for q in cs.trig_problems(t, lg.game_cs)], nm
    assert all(by_rule[r] == tc[r][2] <= tc[r][1] for r in tc), (nm, by_rule, tc)
    assert all(t.count == 375 for t in lg.trigs if t.rule == 0) and all(t.count in (302, 303) for t in lg.trigs if t.rule == 1)
    # P2:302 / 303 區塊依起點與回到點分型;MDI 型(0080:0ed6 → 0x3f1a4)裡沒有硬體中斷
    cls = collections.Counter()
    for t in (t for t in lg.trigs if t.rule == 1):
        back = [x for x in t.insns if x.n == t.n1 + 1]
        assert len(back) == 1, (nm, t.seq)
        hw = [q for q in t.irqs if t.n0 <= q.n <= t.n1 and q.type == 0]
        mdi = (t.cs, t.eip) == MDI_FROM and back[0].cs == lg.game_cs and back[0].eip - DELTA == MDI_BACK
        if mdi:
            assert not hw, (nm, t.seq, hw)
        cls[("mdi" if mdi else f"{t.cs:04x}:{t.eip:x}->{back[0].cs:04x}:{back[0].eip:x}", t.count, len(hw))] += 1
    assert sum(cls.values()) == by_rule[1], (nm, cls, by_rule)
    (_k0, m375, w375), (_k1, m302, w302) = tc[0], tc[1]
    assert (w375, w302) == (by_rule[0], by_rule[1]), (nm, tc, by_rule)
    # P1:375 區塊(本輪三次都沒有時不進這裡)
    p1 = []
    for t in (t for t in lg.trigs if t.rule == 0):
        iq = [(q.num, q.type, q.m, q.cs, q.eip) for q in t.irqs if t.n0 <= q.n <= t.n1]
        drv = [x for x in t.span() if x.cs == 0x137C]
        p1.append(iq == [(0x0F, 0, "r", 0x0C5C, 0x1FAD)] and len(drv) == 375 - 302 and (drv[0].eip, drv[-1].eip) == (0x682, 0x729))
    assert all(p1), (nm, p1)
    RUNS[nm] = {"calllog": rel(p), "md5": m5, "tail_cut": lg.tail_cut,
                "yc": {"ng_375": {"matched": m375, "written": w375}, "ng_302_303": {"matched": m302, "written": w302}},
                "yn": dict(sorted(lg.trig_spans.items())),
                "blocks_302_303": {f"{kind} {cnt} hw_irq={nhw}": v for (kind, cnt, nhw), v in sorted(cls.items())},
                "yi_records_in_302_303_blocks": sum(len(t.irqs) for t in lg.trigs if t.rule == 1), "p1_blocks": len(p1)}
N375 = sum(r["yc"]["ng_375"]["matched"] for r in RUNS.values())
N_MDI = sum(v for r in RUNS.values() for k, v in r["blocks_302_303"].items() if k.startswith("mdi "))
N_NG = sum(r["yn"]["ng"] for r in RUNS.values())
assert N_MDI > 0 and N_NG > 0
VERDICT = {"P1": "NOT TESTED" if N375 == 0 else "PASS", "P2": "PASS", "P3": "記錄", "P4": "PASS"}
# 沒有任何 375 區塊被檢查時不能寫 PASS(寫出數 = 區塊數已在上面核過)
assert (VERDICT["P1"] == "NOT TESTED") == (sum(r["p1_blocks"] for r in RUNS.values()) == 0), VERDICT
OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s181b.py"), "exe_md5": MD5, "prediction": rel(PRED), "driver": rel(DRV / "lc181.py"),
    "approval": "使用者 2026-11-01「全部依照你的建議自動進行處理」;計畫三次、失敗即停(三次都正常結束)",
    "trig": TRIG, "runs": RUNS, "verdict": VERDICT,
    "conclusion": f"三次共 {N_NG} 個非遊戲區間,ng 375 符合 {N375} 次:P1 {VERDICT['P1']},「375 = MDI 型重入夾一次 IRQ 7」的直接觀察仍只有"
                  f" lc174a #24 一次。MDI 型 302 / 303 區塊 {N_MDI} 個都沒有硬體中斷(P2 PASS)。lc163a / lc167a 兩項維持 INFERRED + 獨立佐證;"
                  "這個場景(標題 → START → 靜置)裡這型太少,再加次數也很難改變分母。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, VERDICT)
