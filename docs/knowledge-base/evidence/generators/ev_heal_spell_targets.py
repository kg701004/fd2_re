"""治療法術各次 collect_targets_in_range 傾印與恢復量量測的證據 JSON(doc98 續四十七)。"""
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
D = ROOT / ".wsl_build" / "ctr"
OUT = out_path("heal_spell_targets_20260929.json")
W, H, N = 27, 21, 21


def side_ok(sel: int, side: int) -> bool:
    return {0: side == 0, 1: side != 0, 2: side == 1, 3: side == 2}[sel]


rounds = {}
for tag in ("hA1", "hA2", "hB0", "hB1", "hB2"):
    stack = (D / f"{tag}_stack.bin").read_bytes()
    cells = (D / f"{tag}_map.bin").read_bytes()
    units = (D / f"{tag}_units.bin").read_bytes()
    count, = struct.unpack_from("<I", stack, 0)
    ret, ox, oy, outp, rng, thr, sel = struct.unpack_from("<7I", stack, 0x14)
    mark = lambda x, y: cells[7 + 4 * (y * W + x)]
    rows, pred = [], []
    for i in range(N):
        r = units[i * 80:(i + 1) * 80]
        x, y, f5, side = r[0], r[1], r[5], r[6]
        m = mark(x, y)
        inc = not (f5 & 1) and m != 0xFF and side_ok(sel, side)
        if m != 0xFF or inc:
            rows.append({"unit": i, "x": x, "y": y, "side": side, "flags5": f5, "cell_mark": m, "predicted_in": inc})
        if inc:
            pred.append(i)
    rec = {
        "return_address_static": hex(ret - 0x19C000), "origin": [ox, oy], "out_buf_live": hex(outp),
        "range": rng, "threshold": thr, "selector": sel, "returned_count": count, "predicted": pred,
        "units_on_marked_cells": rows,
        "marked_cells": {f"{x},{y}": mark(x, y) for y in range(H) for x in range(W) if mark(x, y) != 0xFF},
    }
    if outp:
        out = (D / f"{tag}_out.bin").read_bytes()
        rec["out_buf"] = list(out[:count])
        assert rec["out_buf"] == pred, tag
    else:
        rec["out_buf"] = None
        assert count == len(pred), tag
    rounds[tag] = rec

def w(b: bytes, i: int, o: int) -> int:
    """單位 i(80 byte 記錄)在位移 o 的 16 位元值。"""
    return struct.unpack_from("<H", b, i * 80 + o)[0]


# 法術表(docs/data/exe_tables/spell.json,FD2.EXE 0x7aa11 起每列 7 byte 的靜態解析)
SPELL = json.loads((ROOT / "docs" / "data" / "exe_tables" / "spell.json").read_text(encoding="utf-8"))
assert all(s["id"] == k for k, s in enumerate(SPELL))
# heal_hp_apply 的斷點讀值由當時 bp_loop.sh 的終端輸出(原始紀錄,見 _console.py)解析:
#   入口 0x1c916(EDI = 法術編號、EAX = amount;行尾 "ENTRY ret=0x1b8911 target=T spell=AMOUNT")
#   亂數取餘後 0x1c971(EDX = 亂數、EDI = 目標施法前 HP)。執行期 = 靜態 + 0x19c000。
HEAL_CONSOLE = {"hA": "20260929T123903_toolu_01VUEimRvguo6gZ1twzq9aE7", "hB": "20260929T124135_toolu_01Ya8jPmYNHMPRnSXYw2oCqB"}
PRE_POST = {"hA": ("h0", "post_hA"), "hB": ("post_hA", "post_hB")}  # hB 施法前 = hA 施法後的傾印
EIP_ENTRY, EIP_ROLL = 0x1B8916, 0x1B8971
_ENTRY_TAIL = re.compile(r" ENTRY ret=0x1b8911 target=(\d+) spell=(\d+)$")
_POST_LINE = re.compile(r"(?m)^post (\d+) \((\d+), (\d+)\) side (\d+) f5 0x([0-9a-f]+) race (\d+) class (\d+) HP (\d+) MP (\d+)$")
heals, mp_caster = [], {}
for rnd, stem in HEAL_CONSOLE.items():
    meta, text = _console.load(stem)
    assert _console.invocations(meta["cmd"], "bp_loop.sh") == [[rnd]], (rnd, meta["cmd"])
    pre, post_b = ((D / f"{n}.bin").read_bytes() for n in PRE_POST[rnd])
    # 交叉檢查(終端輸出 ↔ 傾印):同一段輸出最後印出的單位欄位必須等於施法後傾印(證明是同一次執行)
    printed = _POST_LINE.findall(text)
    assert printed, rnd
    for m in printed:
        i = int(m[0])
        r = post_b[i * 80:(i + 1) * 80]
        assert [int(m[1]), int(m[2]), int(m[3]), int(m[4], 16), int(m[5]), int(m[6]), int(m[7]), int(m[8])] == \
            [r[0], r[1], r[6], r[5], r[0x1F], r[0x20], w(r, 0, 0x40), w(r, 0, 0x44)], (rnd, m)
    lines = [ln.strip() for ln in text.splitlines() if ln.startswith("stop ")]
    st = _console.stops(text)
    assert len(st) == len(lines) and len(st) % 2 == 0 and st, rnd
    targets = []
    for k in range(0, len(st), 2):
        e, r = st[k], st[k + 1]
        assert (e["EIP"], r["EIP"]) == (EIP_ENTRY, EIP_ROLL), (rnd, k)
        m = _ENTRY_TAIL.search(lines[k])
        assert m and not _ENTRY_TAIL.search(lines[k + 1]), (rnd, lines[k])
        t, amount, spell = int(m[1]), int(m[2]), e["EDI"]
        assert e["EAX"] == amount == SPELL[spell]["dmg"], (rnd, t, amount, spell)
        hp_before, max_hp = w(pre, t, 0x40), w(pre, t, 0x42)
        assert r["EDI"] == hp_before and w(post_b, t, 0x42) == max_hp, (rnd, t, r["EDI"], hp_before)
        p = amount * 9 // 10 + r["EDX"] * amount // 1000
        hp_after = w(post_b, t, 0x40)
        assert min(hp_before + p, max_hp) == hp_after, (rnd, t, p)
        heals.append({"round": rnd, "spell": spell, "amount": amount, "target": t, "roll": r["EDX"], "predicted": p,
                      "hp_before": hp_before, "hp_after": hp_after, "max_hp": max_hp})
        targets.append(t)
    spells = {h["spell"] for h in heals if h["round"] == rnd}
    assert len(spells) == 1, (rnd, spells)
    (spell,) = spells
    # 目標 = 落點那次 collect 的 outBuf;兩次 collect 的 range = 法術列的距離 / 範圍
    assert targets == rounds[f"{rnd}2"]["out_buf"], (rnd, targets)
    assert (rounds[f"{rnd}1"]["range"], rounds[f"{rnd}2"]["range"]) == (SPELL[spell]["dist"], SPELL[spell]["range"]), rnd
    # 非目標單位 HP 不變;MP 只有施法者在變,扣的量 = 法術列 MP
    assert {i for i in range(N) if w(pre, i, 0x40) != w(post_b, i, 0x40)} <= set(targets), rnd
    (mp_caster[rnd],) = [i for i in range(N) if w(pre, i, 0x44) != w(post_b, i, 0x44)]
    assert w(pre, mp_caster[rnd], 0x44) - w(post_b, mp_caster[rnd], 0x44) == SPELL[spell]["mp"], rnd
dumps = {t: (D / f"{t}.bin").read_bytes() for t in ("h0", "post_hA", "post_hB")}
(caster,) = [i for i in range(N) if dumps["h0"][i * 80 + 0x3C] != dumps["post_hB"][i * 80 + 0x3C]]
assert set(mp_caster.values()) == {caster}, (mp_caster, caster)
crec = dumps["h0"][caster * 80:(caster + 1) * 80]
post = {t: b[caster * 80 + 0x3C] for t, b in dumps.items()}
# 累加式的每目標係數與第二因子 40 照 doc98 續四十七抄錄(#5 不計);這裡不另行推導
FACTOR, ROW = {3: 40, 4: 36, 1: 32}, 40


def accumulated(rnd: str) -> int:
    """heal_hp_apply 累加進 [0x53ec8] 的量:係數 × 40 × 恢復量 // MaxHP(恢復量與 MaxHP 取自 heals)。"""
    return sum(FACTOR[h["target"]] * ROW * h["predicted"] // h["max_hp"] for h in heals if h["round"] == rnd and h["target"] in FACTOR)


exp = {
    "caster": caster, "caster_level": crec[0x21], "caster_class": crec[0x20],
    # player_action_ring 0x19029..0x19045:除以施法者等級,職業 > 8 時再 +0x1e(doc98 續四十七的靜態讀法)
    "divisor": crec[0x21] + (0x1E if crec[0x20] > 8 else 0),
    "ex_before": post["h0"], "ex_after_hA": post["post_hA"], "ex_after_hB": post["post_hB"],
    "hA_accumulated": accumulated("hA"), "hB_accumulated": accumulated("hB"),
}
assert exp["ex_after_hA"] - exp["ex_before"] == exp["hA_accumulated"] // exp["divisor"]
assert exp["ex_after_hB"] - exp["ex_after_hA"] == exp["hB_accumulated"] // exp["divisor"]
doc = {
    "note": "DOSBox-X 記憶體傾印與斷點讀值整理;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。collect 的 predicted 依"
            "『+5 bit0 未設、格子記號 != 0xff、陣營符合 selector』離線計算;heal 的 predicted = amount*9//10 + roll*amount//1000。",
    "collect_rounds": rounds, "heals": heals, "experience": exp,
}
OUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", OUT.stat().st_size, exp)
