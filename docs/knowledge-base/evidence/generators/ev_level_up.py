"""升級動態驗證的證據 JSON 與登錄表更新(doc98 續四十九)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
EVI = out_path("level_up_20260929.json")
D = ROOT / ".wsl_build" / "ctr"

# 斷點讀值由當時驅動腳本的終端輸出(原始紀錄,見 _console.py)解析:pending = 0x2fab9(執行期 0x1cbab9)的 EAX;
# gains = 0x1e55a(執行期 0x1ba55a)停點的 EBP,依屬性指標(unit+0x37/0x39/0x3e/0x42/0x46)排成 AP、DP、DX、MaxHP、MaxMP。
# 依時間順序:攻擊前原始讀值、LA 攻擊、LA 對話 3 步、對話 2 步、LA 最終傾印、LB2 攻擊、LB2 對話與最終傾印、LC、LD、LE。
CONSOLE = ["20260929T133650_toolu_01NcNakKdj9hduDCDcgLM6pB", "20260929T133839_toolu_01WKAcAzsMaciJWdHH41HHwe",
           "20260929T133939_toolu_01Th1T2LwkVgsKGUTdxSPpv3", "20260929T134000_toolu_014zhVU89BUWhjfPwFKCsvji",
           "20260929T134020_toolu_01Ak48PgwdTUfRYhWCFjd7Aq", "20260929T134210_toolu_012ZLUnJev3ScLsFUf55kUVZ",
           "20260929T134310_toolu_01Ad1S5cqftdutFkekBpeMkx", "20260929T134429_toolu_01Hq2Z1fZYtkSS22HyCgtksx",
           "20260929T134636_toolu_01YUqzkmyKQkZgZseDBpnfvp", "20260929T134803_toolu_01RxMYwma4U2gJQgXvZPDgyy"]
# 每段輸出所屬的案例 = lvl_test.sh / run_case.sh 的最後一個參數、dlg_step.sh / lvl_print.py 的第一個參數。
# 例外:13:40:00 的 `dlg_step.sh LB 2` 是 LA 升級對話的最後兩步(LB 只用在截圖檔名;LA 的對話 3 步在 13:39:39、
# post_LA.bin 在 13:40:20 才傾印,中間沒有其他攻擊),併入 LA;下面另以屬性指標恰好各出現一次確認。
ALIAS = {"LB": "LA"}
SCRIPTS = (("lvl_test.sh", -1), ("run_case.sh", -1), ("dlg_step.sh", 0), ("lvl_print.py", 0))
STAT_OFF = [0x37, 0x39, 0x3E, 0x42, 0x46]  # 基礎 AP、DP、DX、MaxHP、MaxMP
GAIN_LINE = re.compile(r"(?m)^  stop: EIP=001BA55A gain\(EBP\)=(\d+) stat_ptr=0x([0-9a-f]+) \(unit\+0x([0-9a-f]+)\) "
                       r"growth_ptr=0x([0-9a-f]+) ")
PRINT_LINE = re.compile(r"(?m)^(pre|post) (\d+) lv (\d+) EX (\d+) base AP/DP/DX (\d+) (\d+) (\d+) HP (\d+) (\d+) "
                        r"MP (\d+) (\d+) derived AP DP HIT EV (\d+) (\d+) (\d+) (\d+) bits ([0-9a-f]+) ")
ORIG_LINE = re.compile(r"(?m)^(\d+) port 0x[0-9a-f]+ class \d+ lv \d+ EX \d+ base AP/DP/DX (\d+) (\d+) (\d+) HP .* "
                       r"derived AP DP HIT EV (\d+) (\d+) (\d+) (\d+) bits ")
pending, gain_stops, prints, hexrow, orig = {}, {}, {}, {}, {}
for stem in CONSOLE:
    meta, text = _console.load(stem)
    tags = {ALIAS.get(a[k], a[k]) for line in meta["cmd"].splitlines() for s, k in SCRIPTS
            for a in _console.invocations(line, s)}
    hexrow |= {m[0]: m[1] for m in re.findall(r"(?m)^(growth now|learn now|growth row 0x1e live) ([0-9a-f ]+)$", text)}
    if not tags:  # 攻擊前原始讀值(L0.bin 傾印的同一次指令)
        orig |= {int(m[0]): tuple(int(v) for v in m[1:]) for m in ORIG_LINE.findall(text)}
        continue
    (tag,) = tags
    for s in _console.stops(text):
        if s["EIP"] == 0x1CBAB9:
            assert tag not in pending, tag
            pending[tag] = (s["EAX"], s["EBP"])
    gain_stops.setdefault(tag, []).extend(GAIN_LINE.findall(text))
    prints.setdefault(tag, []).extend(PRINT_LINE.findall(text))
assert sorted(pending) == ["LA", "LB2", "LC", "LD", "LE"], pending
gains, gain_unit = {}, {}
for tag, st in gain_stops.items():
    if st:
        assert [int(m[2], 16) for m in st] == STAT_OFF, (tag, st)
        assert [int(m[3], 16) - int(st[0][3], 16) for m in st] == [0, 2, 4, 6, 8], (tag, st)  # 成長列連續 5 對
        gains[tag] = [int(m[0]) for m in st]
        gain_unit[tag] = {(int(m[1], 16) - 0x26BDC8) // 0x50 for m in st}  # 屬性指標所在的單位序號
assert sorted(gains) == ["LA", "LB2", "LD"], gains
# 成長列上下限(每屬性 [lo, hi) 兩個 byte;上下限相等 = 固定值):LA/LB2 為測試寫入後讀回,LD 為原始列 0x1e
row = lambda h: [tuple(bytes.fromhex(h)[2 * k:2 * k + 2]) for k in range(5)]
ORIG_BOUNDS = {"LA": row(hexrow["growth now"]), "LB2": row(hexrow["growth now"]), "LD": row(hexrow["growth row 0x1e live"])}
# 裝備加值 = 攻擊前原始讀值的 衍生 - 基礎(AP、DP)與 HIT-DX、EV-DX
EQUIP = {i: (orig[i][3] - orig[i][0], orig[i][4] - orig[i][1], orig[i][5] - orig[i][2], orig[i][6] - orig[i][2]) for i in (0, 3)}
L0 = (D / "L0.bin").read_bytes()  # 同一次指令的傾印:印出的原始讀值必須等於它
for i, o in orig.items():
    assert o == tuple(struct.unpack_from("<H", L0, i * 80 + k)[0] for k in (0x37, 0x39, 0x3E, 0x48, 0x4A, 0x4C, 0x4E)), i
assert sorted(orig) == [0, 2, 3, 4], orig
runs = {
    "LA": {"attacker": 0, "growth_row": "05 05 03 03 00 00 07 07 02 02 04 (測試用,上下限相等)", "learn_row": "07 0d ff.. (測試用:7 級學法術 13)"},
    "LB2": {"attacker": 0, "growth_row": "同 LA", "learn_row": "同 LA"},
    "LC": {"attacker": 0, "growth_row": "同 LA", "learn_row": "同 LA"},
    "LD": {"attacker": 3, "growth_row": "07 0e 06 0d 02 04 08 0f 00 00 ff (原始)", "learn_row": None},
    "LE": {"attacker": 3, "growth_row": "同 LD", "learn_row": None},
}
# 說明字串裡的成長列 / 法術列必須等於終端輸出讀回的 byte
assert runs["LA"]["growth_row"].startswith(hexrow["growth now"] + " ")
assert runs["LD"]["growth_row"].startswith(hexrow["growth row 0x1e live"] + " ")
assert runs["LA"]["learn_row"].startswith(hexrow["learn now"][:8] + "..") and set(hexrow["learn now"][6:].split()) == {"ff"}
for tag, info in runs.items():
    # 0x2fab9 停點的 EBP = 攻方記錄位址,必須是該案例的攻方
    assert pending[tag][1] == 0x26BDC8 + info["attacker"] * 0x50, (tag, hex(pending[tag][1]))
    assert gain_unit.get(tag, {info["attacker"]}) == {info["attacker"]}, (tag, gain_unit.get(tag))
    runs[tag] = {"attacker": info["attacker"], "pending": pending[tag][0], "gains": gains.get(tag),
                 "growth_row": info["growth_row"], "learn_row": info["learn_row"]}


def fields(r: bytes) -> dict:
    w = lambda o: struct.unpack_from("<H", r, o)[0]
    return {"level": r[0x21], "ex": r[0x3C], "base_ap": w(0x37), "base_dp": w(0x39), "base_dx": w(0x3E), "hp": w(0x40),
            "max_hp": w(0x42), "mp": w(0x44), "max_mp": w(0x46), "ap": w(0x48), "dp": w(0x4A), "hit": w(0x4C), "ev": w(0x4E),
            "portrait": r[7], "spell_bits": r[0x1A:0x1F].hex()}


cases = []
for tag, info in runs.items():
    i = info["attacker"]
    pre = fields((D / f"pre_{tag}.bin").read_bytes()[i * 80:(i + 1) * 80])
    post = fields((D / f"post_{tag}.bin").read_bytes()[i * 80:(i + 1) * 80])
    cap = 0x63 if pre["portrait"] in (0x1E, 0x1F) else 0x28
    if pre["level"] == cap:
        exp_level, exp_ex, leveled = pre["level"], pre["ex"], False
    else:
        total = pre["ex"] + info["pending"]
        leveled = total >= 100
        exp_level = pre["level"] + (1 if leveled else 0)
        exp_ex = total - 100 if leveled else total
        if leveled and ((pre["portrait"] in (0x1E, 0x1F) and exp_level == 0x63) or
                        (pre["portrait"] not in (0x1E, 0x1F) and exp_level == 0x1E)):
            exp_ex = 0
    assert (post["level"], post["ex"]) == (exp_level, exp_ex), (tag, post, exp_level, exp_ex)
    assert leveled == (info["gains"] is not None), tag
    # 終端輸出印出的攻方欄位必須等於該案例的傾印(證明輸出與傾印是同一次執行):每次印的 pre 都等於 pre 傾印,
    # 最後一次印的 post 等於最終 post 傾印(較早印的 post 是對話推進前、之後被覆寫的狀態)
    pr = [m for m in prints[tag] if int(m[1]) == i]
    flat = lambda f: (f["level"], f["ex"], f["base_ap"], f["base_dp"], f["base_dx"], f["hp"], f["max_hp"], f["mp"], f["max_mp"],
                      f["ap"], f["dp"], f["hit"], f["ev"], f["spell_bits"])
    as_tuple = lambda m: tuple(int(v) for v in m[2:15]) + (m[15],)
    assert [m[0] for m in pr].count("pre") >= 1 and pr[-1][0] == "post", (tag, pr)
    assert all(as_tuple(m) == flat(pre) for m in pr if m[0] == "pre"), tag
    assert as_tuple(pr[-1]) == flat(post), (tag, pr[-1])
    if leveled:
        g = info["gains"]
        assert post["base_ap"] - pre["base_ap"] == g[0] and post["base_dp"] - pre["base_dp"] == g[1]
        assert post["base_dx"] - pre["base_dx"] == g[2] and post["max_hp"] - pre["max_hp"] == g[3]
        assert post["max_mp"] - pre["max_mp"] == g[4] and post["hp"] == pre["hp"] and post["mp"] == pre["mp"]
        e = EQUIP[i]
        assert (post["ap"], post["dp"], post["hit"], post["ev"]) == (
            post["base_ap"] + e[0], post["base_dp"] + e[1], post["base_dx"] + e[2], post["base_dx"] + e[3]), tag
        for (lo, hi), v in zip(ORIG_BOUNDS.get(tag, []), g):
            assert (v == lo) if hi == lo else (lo <= v < hi), (tag, lo, hi, v)
    else:
        assert all(post[k] == pre[k] for k in pre), tag
    cases.append({"case": tag, **info, "level_cap": cap, "leveled": leveled, "predicted_level": exp_level,
                  "predicted_ex": exp_ex, "before": pre, "after": post})
assert cases[0]["before"]["spell_bits"] == "001180030f" and cases[0]["after"]["spell_bits"] == "003180030f"
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 記憶體傾印(攻擊前、對話推進完後的攻方記錄)與斷點讀值整理;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "before 的 ap/dp/hit/ev 是測試寫入的 19/0/250/0,升級後被 recalc_equipped_stats 覆蓋。",
    "cases": cases,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok", [(c["case"], c["after"]["level"], c["after"]["ex"]) for c in cases])
