"""ev_lut_circle_ramp_at_unit.py 的變異測試:每個變異改一個判準 / 預測,必須讓產生器以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("半寬係數 11 / 10", "hw = int(math.sqrt(r * r - dy * dy) * 12 / 10)", "hw = int(math.sqrt(r * r - dy * dy) * 11 / 10)"),
    ("裂地術起始半徑 31", "276, 42, 30, 16, PANEL + U1)", "276, 42, 31, 16, PANEL + U1)"),
    ("邊緣命中門檻 1.5", 'r["edge_ok"] < 0.9 * r["edge_rows"]', 'r["edge_ok"] < 1.5 * r["edge_rows"]'),
    ("視窗左緣 5", "VX0, VY0, VW, VH = 4, 4, 0x138, 0xC0", "VX0, VY0, VW, VH = 5, 4, 0x138, 0xC0"),
    ("對照預期 PASS", 'assert set(ctl.values()) == {"FAIL"}, ctl', 'assert set(ctl.values()) == {"PASS"}, ctl'),
    ("拼接間距 325", "sh.paste(frame_rgb(tag, k), ((k % 5) * 324,", "sh.paste(frame_rgb(tag, k), ((k % 5) * 325,"),
    ("調色盤 × 4", "(v & 0x3F) * 255 // 63", "(v & 0x3F) * 4"),
    ("視窗截圖換一張", 'WINDOW = ("lut_circle_ramp_spell12_window_20261013.png", S / "060_Return.png")',
     'WINDOW = ("lut_circle_ramp_spell12_window_20261013.png", S / "061_live12.png")'),
    ("截圖裁切下移 8", ".crop((192, 201, 832, 601))", ".crop((192, 209, 832, 609))"),
    ("截圖對到的幀預期倒退", "assert len(seq) == len(SHOTS[tag]) and seq == sorted(seq), (tag, seq)",
     "assert len(seq) == len(SHOTS[tag]) and seq != sorted(seq), (tag, seq)"),
    ("第一張截圖預期第 0 幀", '== ["s12_f01", "s12_f04"', '== ["s12_f00", "s12_f04"'),
    ("負對照預期有幀", 'assert out["negative_run"]["frames"] == 0', 'assert out["negative_run"]["frames"] == 1'),
    ("記錄增量反號", '== ([cx, cy], r0, step), tag', '== ([cx, cy], r0, -step), tag'),
    # 續一百五十五:資訊框由 draw_map_hud + FDOTHER #5 定、單位格由 FDICON 單位圖比對定
    ("資訊框選另一個位置", "[h for h in _hit if h[1]]", "[h for h in _hit if not h[1]]"),
    ("A / D 數字區右移 8", "or x >= TERR_X and y >= TERR_Y", "or x >= TERR_X + 8 and y >= TERR_Y"),
    ("單位格改看基準畫面", 'np.frombuffer((D / f"{tag}_f{i:02d}.bin")', 'np.frombuffer((D / f"{tag}_ref.bin")'),
    ("單位格接受全透明的圖", " & m.any(axis=(1, 2))).any():", ").any():"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_lut_circle_ramp_at_unit", MUTANTS))
