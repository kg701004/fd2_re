"""續一百七十四 實機核對:lc174a / lc174b 的觸發區塊對 pred174.txt 的 P1 .. P6(每項 assert;失敗即 AssertionError)。

用法:python check174.py [<lc174a CALLLOG> <lc174b CALLLOG>]   (預設 .wsl_build/lc174_live/)
紀錄檔不進 repo,先比 md5(teardown 之後的指紋)。解析與區塊自核都用 tools/calllog_segments.py。
"""
from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "tools"))
import calllog_segments as cls  # noqa: E402

MD5 = {"lc174a": "0aaee51798ec85a779a95aa78ed85cac", "lc174b": "9be49f776cc0ed2fbbc3d7e962503b14"}
DELTA = 0x19C000  # 遊戲 selector 的執行期位址 = 靜態 + DELTA(同 ev_s173)


def rt(a: int) -> int:
    return a + DELTA


def ends(t: cls.Trig) -> tuple[cls.Insn, cls.Insn, cls.Insn]:
    """區間第一條、最後一條、結束那一條。"""
    s = t.span()
    return s[0], s[-1], next(x for x in t.insns if x.n == t.n1 + 1)


def dig_type(t: cls.Trig) -> bool:
    """DIG 服務的長關中斷:ret(0x3f0ab,0x3f0aa cli 之後).. sti(0x3f0bc),結束那一條 pop ebp(0x3f0bd,IF = 1)。"""
    f, last, a = ends(t)
    return (t.kind == "if" and (f.cs, f.eip) == (0x170, rt(0x3F0AB)) and (last.cs, last.eip) == (0x170, rt(0x3F0BC))
            and (a.cs, a.eip, a.iff) == (0x170, rt(0x3F0BD), 1))


def main(argv: list[str]) -> int:
    base = REPO / ".wsl_build" / "lc174_live"
    paths = {"lc174a": Path(argv[0]) if argv else base / "lc174a_CALLLOG.TXT",
             "lc174b": Path(argv[1]) if len(argv) > 1 else base / "lc174b_CALLLOG.TXT"}
    for k, p in paths.items():
        assert hashlib.md5(p.read_bytes()).hexdigest() == MD5[k], (k, p)
    a = cls._read(str(paths["lc174a"]))
    b = cls._read(str(paths["lc174b"]))
    # P1:每個區塊都有 YE,解析端另寫的判準沒有問題
    for name, lg in (("lc174a", a), ("lc174b", b)):
        assert lg.trigs and all(t.complete for t in lg.trigs), name
        bad = {t.seq: cls.trig_problems(t, lg.game_cs) for t in lg.trigs if cls.trig_problems(t, lg.game_cs)}
        assert bad == {}, (name, bad)
    # lc174a 的工具缺口(修正前的二進位):被砍掉 -> 沒有 YC / YN,最後一行寫到一半
    assert a.tail_cut and a.trig_counts == {} and a.trig_spans == {}
    # P2:DIG 型 if 區塊,區間全在 cs 0170;同一份紀錄的 G 一筆涵蓋 ISR 進入 .. 結束那一條,條數 = 前段 + 區間 + 1
    dig = [t for t in a.trigs if dig_type(t)]
    assert Counter(t.count for t in dig) == Counter({43928: 6, 43929: 1}), [(t.seq, t.count) for t in dig]
    g_rows = []
    for t in dig:
        assert all((x.m, x.cs) == ("P", 0x170) for x in t.span())
        ov = [r for r in a.runs if r.n_end >= t.n0 and r.n_start < t.n1 + 1]
        assert len(ov) == 1 and (ov[0].m, ov[0].cs, ov[0].e1) == ("P", 0x170, rt(0x3F0BD)), t.seq
        r = ov[0]
        assert r.n_start < t.n0 and r.n_end == t.n1 + 1
        g_rows.append((t.seq, r.count, t.n0 - r.n_start - 1, t.count))
    assert all(cnt == pre + c + 1 for _s, cnt, pre, c in g_rows) and min(r[1] for r in g_rows) < 44077
    starts = Counter(next(r for r in a.runs if r.n_end >= t.n0 and r.n_start < t.n1 + 1).e0 for t in dig)
    assert starts == Counter({rt(0x3EA8E): 5, rt(0x3F1A4): 2}), starts
    # P4:lc174b 被砍掉後仍有最後一組統計;寫出數 = 區塊數 <= 符合數
    nb = Counter(t.rule for t in b.trigs)
    assert b.tail_cut and set(b.trig_counts) == {0, 1, 2, 3} and set(b.trig_spans) == {"ng", "if"}
    assert all(w == nb.get(r, 0) and w <= m for r, (_k, m, w) in b.trig_counts.items()), (b.trig_counts, nb)
    # P5:TRIGT 9500-24000
    assert min(t.t1 for t in b.trigs) >= 9500
    # P6:START 放開鍵之後 10 ms 內:DIG 型 if 區塊結束,接著 ng 600 .. 604(0080:0ed6 起、0x3f0be 結束、IRQ 1 在 0080:06ca)
    tb = [k.t for k in b.keys if k.data == 0x09C][-1]
    p6_if = [t for t in b.trigs if dig_type(t) and tb < t.t1 < tb + 10]
    p6_ng = [t for t in b.trigs if t.kind == "ng" and 600 <= t.count <= 604 and tb < t.t1 < tb + 10
             and (ends(t)[0].cs, ends(t)[0].eip) == (0x80, 0xED6) and (ends(t)[2].cs, ends(t)[2].eip) == (0x170, rt(0x3F0BE))
             and any((q.num, q.cs, q.eip) == (9, 0x80, 0x6CA) for q in t.irqs)]
    assert len(p6_if) == 1 and len(p6_ng) == 1 and p6_if[0].t1 <= p6_ng[0].t0, (p6_if, p6_ng)
    irq1 = next(q for q in p6_ng[0].irqs if q.num == 9)
    # 同型在 lc174a(#13,START 那一下)
    a_ng = [t for t in a.trigs if t.kind == "ng" and (ends(t)[0].cs, ends(t)[0].eip) == (0x80, 0xED6)
            and any((q.num, q.cs, q.eip) == (9, 0x80, 0x6CA) for q in t.irqs)]
    assert [(t.seq, t.count) for t in a_ng] == [(13, 601)], a_ng
    print("lc174a: blocks", len(a.trigs), "per rule", dict(Counter(t.rule for t in a.trigs)), "DIG-type G rows", g_rows)
    print("lc174b: blocks", len(b.trigs), "YC", b.trig_counts, "YN", b.trig_spans)
    print(f"lc174b START: break {tb:.4f}; DIG if #{p6_if[0].seq} {p6_if[0].t0:.4f}..{p6_if[0].t1:.4f} ({p6_if[0].count});"
          f" ng #{p6_ng[0].seq} {p6_ng[0].count}, IRQ 1 at {irq1.t:.4f} (+{irq1.t - tb:.4f} ms)")
    print("check174: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
