"""一次性:確認新增的交叉檢查會失敗(在記憶體中改動新產生器原始碼後執行,預期 AssertionError)。"""
from __future__ import annotations

import os
import tempfile
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parent
HERE = Path(__file__).parent
os.environ["FD2_EVIDENCE_OUT_DIR"] = tempfile.mkdtemp()
(HERE / "mut_out").mkdir(exist_ok=True)
sys.path.insert(0, str(GEN))
os.chdir(GEN)

M1P, M2P = "20260929T145133_toolu_013yFpSAjgHNYjfCRxkHThAp", "20260929T145348_toolu_01HZESbratRbtoBt7nFWYDd1"
C1P, C2P = "20260929T152822_toolu_017ub1ji95mkXhEuRxnvtUDh", "20260929T153239_toolu_018jSC3D1yMzzVMj8Wv7daWk"
A2S = '"A2": {"setup": ("a2", "20260930T014249_toolu_015Ga1xJhodH5Eo2z7ZuFmBN")'
MUTS = {
    "ev_attack_path_selection": [
        ("無變異(對照)", None, None),
        ("M1/M2 攻擊後印出互換", f'"post_print": "{M1P}"', f'"post_print": "{M2P}"'),
        ("M3 第 5、6 擊攻方互換", "(13, 9, 24, 1, 8, 0), (17, 9, 24, 1, 8, 0)", "(17, 9, 24, 1, 8, 0), (13, 9, 24, 1, 8, 0)"),
        # 改用 HP 上限 0x42 的變異在此不具鑑別力(印出的單位攻擊前 HP 都是滿的),改為 AP/DP 位移互換
        ("M1 攻擊前印出 AP/DP 位移互換", "for o in (0x40, 0x48, 0x4A, 0x4C, 0x4E)", "for o in (0x40, 0x4A, 0x48, 0x4C, 0x4E)"),
        ("M2 旗標改 1", '"M2": {"flag_53af9": 0', '"M2": {"flag_53af9": 1'),
    ],
    "ev_ai_spell_path": [
        ("無變異(對照)", None, None),
        ("C1/C2 施法後印出互換", f'"post_print": "{C1P}"', f'"post_print": "{C2P}"'),
        ("單位表基址偏 1 筆", "UNITS, REC = 0x26BDC8, 0x50", "UNITS, REC = 0x26BD78, 0x50"),
        # 改用 MP 上限的變異不具鑑別力(施法前 MP 都是滿的),改為法術位元欄錯位一格
        ("C1 設定印出法術位元欄錯位", "b[0x1A:0x1F].hex(), b[0xA], b[0xB]]", "b[0x1B:0x20].hex(), b[0xA], b[0xB]]"),
    ],
    "ev_spell9_path": [
        ("無變異(對照)", None, None),
        ("A2 設定改指向 p2", A2S, '"A2": {"setup": ("p2", "20260930T013831_toolu_013s7XZv1zg8zbhSVC3Hr6w5")'),
        ("A1 傾印印出改指向 A2 那次", '"dump_print": "20260930T014039_toolu_01Wee3sVsJcCFTvKKLBnBvgu"},\n    "A2"',
         '"dump_print": "20260930T014249_toolu_015Ga1xJhodH5Eo2z7ZuFmBN"},\n    "A2"'),
        ("A1 目標改 #0", '"A1": {"caster": 11, "flag": 0, "pre": "s9_pre_a1", "post": "s9_post_a1", "target": 1}',
         '"A1": {"caster": 11, "flag": 0, "pre": "s9_pre_a1", "post": "s9_post_a1", "target": 0}'),
    ],
}
bad = 0
for name, muts in MUTS.items():
    src = (GEN / f"{name}.py").read_text(encoding="utf-8")
    for label, a, b in muts:
        s = src
        if a is not None:
            assert s.count(a) == 1, (name, label)
            s = s.replace(a, b)
        try:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(s, name, "exec"), {"__file__": str(GEN / f"{name}.py"), "__name__": "__main__"})
            res = "PASS"
        except AssertionError as e:
            res = f"AssertionError {str(e)[:80]}"
        except Exception as e:  # 其他例外(KeyError 等)不算「檢查擋下」
            res = f"OTHER {type(e).__name__} {str(e)[:80]}"
        ok = (res == "PASS") if a is None else res.startswith("AssertionError")
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {name} [{label}] -> {res}")
print("all mutations caught" if not bad else f"{bad} unexpected")
sys.exit(1 if bad else 0)
