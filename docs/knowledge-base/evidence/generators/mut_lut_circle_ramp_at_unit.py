"""ev_lut_circle_ramp_at_unit.py 的變異測試:每個變異改一個判準 / 預測,必須讓產生器以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("半寬係數 11", 'SCALE = operand(0x2194A, "push ")', 'SCALE = operand(0x2194A, "push ") - 1'),
    ("裂地術起始半徑 31", "276, 42, 30, 16, PANEL + U1 +", "276, 42, 31, 16, PANEL + U1 +"),
    ("換色段右端含 cx + hw", "VX0 + min(cx + hw + right, VW)", "VX0 + min(cx + hw + right + 1, VW)"),
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
    ("單位格改看基準畫面", 'np.frombuffer((D / f"{tag}_f{i:02d}.bin").read_bytes(), np.uint8).reshape(-1, W)\n    cells',
     'np.frombuffer((D / f"{tag}_ref.bin").read_bytes(), np.uint8).reshape(-1, W)\n    cells'),
    ("單位格接受全透明的圖", " & m.any(axis=(1, 2))).any():", ").any():"),
    # 續一百五十六:逐像素預測(0x219ad + FDOTHER #3)、游標格
    ("換色表取第 i + 1 項", "LUTS = [bank_lut(i) for i in range(10)]", "LUTS = [bank_lut(i + 1) for i in range(10)]"),
    ("s12 不排除游標格", 'PANEL + U1 + CURSOR["s12"]),', "PANEL + U1),"),
    ("游標格右移一格", "CURSOR = {t: [cell_box(*CASTER[t])] for t in _LOG}",
     "CURSOR = {t: [cell_box(CASTER[t][0] + 1, CASTER[t][1])] for t in _LOG}"),
    ("byte3 換色表不限三角表的階", "HI_STEPS = sorted(set(_TRI))", "HI_STEPS = list(range(23))"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_lut_circle_ramp_at_unit", MUTANTS))
