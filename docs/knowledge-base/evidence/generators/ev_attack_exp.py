"""物理攻擊經驗值動態驗證的登錄表更新與證據 JSON(doc98 續四十八)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
EVI = out_path("attack_exp_20260929.json")
D = ROOT / ".wsl_build" / "ctr"

E_ROW = 21
# --- 證據:由傾印重算;斷點讀值由當時 exp_test.sh 的終端輸出(原始紀錄,見 _console.py)解析 ---
CONSOLE = ["20260929T125754_toolu_01YX3jRW1dkndYN4W3PHquVA", "20260929T130008_toolu_01Ka26U6gc1BeJJrnX1Zzcj3",
           "20260929T130212_toolu_01NVVNwyZxgzzucD2m94uaf5"]
bp, post_ex_console = {}, {}
for stem in CONSOLE:
    for args, seg in _console.segments(stem, "exp_test.sh"):
        tag = args[-1]  # exp_test.sh 的最後一個參數 = 案例標籤(傾印檔名 pre_<tag>.bin / post_<tag>.bin)
        eax = {s["EIP"]: s["EAX"] for s in _console.stops(seg)}
        assert set(eax) <= {0x1CBA9F, 0x1CBAB9}, (tag, eax)  # 執行期 = 靜態 + 0x19c000
        bp[tag] = (eax[0x1CBA9F], eax.get(0x1CBAB9))
        post_ex_console[tag] = {int(m[0]): int(m[1]) for m in re.findall(r"(?m)^post (\d+) .* EX (\d+) HP", seg)}
assert sorted(bp) == ["xA", "xB", "xC", "xD", "xE"], bp
att = {"xA": 0, "xB": 2, "xC": 4, "xD": 3, "xE": 3}
cases = []
for tag in ("xA", "xB", "xC", "xD", "xE"):
    pre = (D / f"pre_{tag}.bin").read_bytes()
    post = (D / f"post_{tag}.bin").read_bytes()
    a, d0, a1, d1 = (b[i * 80:(i + 1) * 80] for b, i in ((pre, att[tag]), (pre, 11), (post, att[tag]), (post, 11)))
    w = lambda r, o: struct.unpack_from("<H", r, o)[0]
    lv = a[0x21] + (0x1E if (8 < a[0x20] < 0x19 or a[8] == 0x1C) else 0)
    base = d0[0x21] * E_ROW // lv
    dmg = w(d0, 0x40) - w(d1, 0x40)
    killed = w(d1, 0x40) == 0
    exp = base if killed else base * dmg // w(d0, 0x42)
    gain = a1[0x3C] - a[0x3C]
    # 同一段終端輸出印出的攻擊後 EX 必須等於該案例的傾印(證明這段輸出與傾印是同一次執行)
    assert post_ex_console[tag][att[tag]] == a1[0x3C], (tag, post_ex_console[tag])
    rec = {
        "case": tag, "attacker": att[tag], "attacker_level": a[0x21], "attacker_class": a[0x20], "attacker_byte8": a[8],
        "divisor": lv, "defender_level": d0[0x21], "defender_portrait": d0[7], "row_plus9": E_ROW,
        "defender_hp_before": w(d0, 0x40), "defender_hp_after": w(d1, 0x40), "defender_max_hp": w(d0, 0x42),
        "damage": dmg, "killed": killed, "predicted_base": base, "predicted_exp": exp, "predicted_gain": min(exp, 99),
        "bp_0x2fa9f_eax": bp[tag][0], "bp_0x2fab9_eax": bp[tag][1], "attacker_ex_before": a[0x3C], "attacker_ex_after": a1[0x3C],
        "defender_flags5_before": d0[5], "defender_flags5_after": d1[5],
        "guide_formula_would_give": min(99, (d0[0x21] * E_ROW * d0[0x21] // lv) * (w(d0, 0x42) if killed else dmg) // w(d0, 0x42)),
    }
    assert base == bp[tag][0] and gain == min(exp, 99), tag
    assert (bp[tag][1] is None) == killed and (killed or bp[tag][1] == exp), tag
    assert rec["guide_formula_would_give"] != rec["predicted_gain"] or tag == "xE", tag
    cases.append(rec)
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 記憶體傾印(攻擊前後的單位記錄)與斷點讀值整理;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "predicted 依 scene_attack_resolve 0x2fa4d..0x2fab9 的靜態公式計算;guide_formula_would_give 是攻略字面公式"
            "(守方等級出現兩次)的預測,用來顯示兩者可區分。",
    "cases": cases,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok", [(c["case"], c["predicted_gain"], c["guide_formula_would_give"]) for c in cases])
