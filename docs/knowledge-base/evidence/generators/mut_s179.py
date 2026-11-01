"""ev_s179.py 的變異測試:每個變異改一個判準 / 預測 / 解讀,必須讓 ev_s179.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (T) 標題三段
    ("標題載入的資源當成 #49", 'RES_TITLE = operand(0x1F8D6, "push ")', 'RES_TITLE = 49 + 0 * operand(0x1F8D6, "push ")'),
    ("第 3 段讀成確認段", 'IDX_TITLE = operand(0x1FD1E, "push ")', 'IDX_TITLE = operand(0x1FED5, "push ")'),
    ("指標處比 #49 的開頭", 'assert pl.mem_prefix["s1"] == H77, nm', 'assert pl.mem_prefix["s1"] == OTHER_HEADS["#49"], nm'),
    ("#49 / #53 開頭與 #77 相同", "all(h != H77 for h in OTHER_HEADS.values())", "all(h == H77 for h in OTHER_HEADS.values())"),
    ("播放在載入之前", "pl.line > ld.line", "pl.line < ld.line"),
    ("載入回的指標不是播放的", "assert r.eax == pl.stack[0], (nm, hex(r.eax))", "assert r.eax != pl.stack[0], (nm, hex(r.eax))"),
    ("確認音效拿第 3 段", "c.stack[1] == IDX_CONFIRM for c in conf", "c.stack[1] == IDX_TITLE for c in conf"),
    ("動畫放第 1 段", 'c.mem_prefix["s1"] == H78 and c.stack[1] == 0 for c in ani', 'c.mem_prefix["s1"] == H78 and c.stack[1] == 1 for c in ani'),
    ("混音序列確認在前", "[[K_ANI], [tuple(x) for x in SND_TITLE[\"where\"]], [K_CONF]]",
     "[[K_CONF], [tuple(x) for x in SND_TITLE[\"where\"]], [K_ANI]]"),
    ("標題段在選單之後才開始", 's_title["end"] < t_fd7c < t_fed3', 's_title["start"] > t_fd7c < t_fed3'),
    ("確認後第一次混音改看之前", "nxt = next(f for f in mix if f[0] > t_fed3)", "nxt = next(f for f in mix if f[0] < t_fed3)"),
    ("開場音效在開始之前", 's["start"] > t_new for s in pool_snd', 's["start"] < t_new for s in pool_snd'),
    # (I) UI 音效池
    ("index 9 改看飛行那支", 'IDX_STEP = operand(0x322C7, "push ")', 'IDX_STEP = operand(0x32280, "push ")'),
    ("打字聲改看 index 7", 'IDX_TYPE = operand(0x1653E, "push ")', 'IDX_TYPE = operand(0x34176, "push ")'),
    ("跳入推音效池那條不算", "for src, mn in BRANCH.get(buf.address, []):", "for src, mn in BRANCH.get(buf.address + 1, []):"),
    ("防拷 jmp 沒跳過呼叫", "_skip > 0x118AC + INSNS[_IX[0x118AC]].size", "_skip < 0x118AC"),
    ("fixup 對照拿不存在的目標", "assert 0x35854 in _FX", "assert 0x35855 in _FX"),
    ("打字聲的呼叫者當成防拷", "set(POOL_CALLERS[IDX_TYPE]) == {RET_TYPE}", "set(POOL_CALLERS[IDX_TYPE]) == {0x3412B}"),
    ("音效池開頭拿 #77", "res(RES_ANI)[:HEAD], res(RES_POOL)[:HEAD]", "res(RES_ANI)[:HEAD], res(RES_TITLE)[:HEAD]"),
    ("每份次數多算一個", 'ORDER[nm]["pool_sounds"][f"#{RES_POOL}/{w[\'where\'][0][2]}"] == n',
     'ORDER[nm]["pool_sounds"][f"#{RES_POOL}/{w[\'where\'][0][2]}"] == n + 1'),
    # (R) 中斷號
    ("填緩衝門檻取下群", "    return gs[k]\n", "    return gs[k - 1]\n"),
    ("375 的間隔與正向對照不同", 'R375["next_dig_dt_ms"] == P375["next_dig_dt_ms"]', 'R375["next_dig_dt_ms"] != P375["next_dig_dt_ms"]'),
    ("對照組改看 304", "CTRL_NG = (302, 303)", "CTRL_NG = (302, 304)"),
    ("正向對照當成 IRQ 1", '["irq"].split()[0] == "0f"', '["irq"].split()[0] == "09"'),
    ("續一百六十五 375 兩次", '"302": 14, "375": 1}', '"302": 14, "375": 2}'),
    ("主機時間換算反向", "return L0 + (h - H0) * 1000 * RATE", "return L0 - (h - H0) * 1000 * RATE"),
    ("送鍵後等兩倍", '["findempty_001_Up.png"] - SLEEP_DIR)', '["findempty_001_Up.png"] - 2 * SLEEP_DIR)'),
    ("先送鍵再截起點圖", "('\"findempty_000_start.png\"', \"send_keys(name, direction)\",",
     "(\"send_keys(name, direction)\", '\"findempty_000_start.png\"',"),
    ("最後送鍵只看逐鍵腳本", 'LAST_KEY = max([L0] + [s["t"] for s in _steps])', 'LAST_KEY = max([s["t"] for s in _steps])'),
    ("558 離送鍵很近", "assert GAP558 > 20000, GAP558", "assert GAP558 < 20000, GAP558"),
    # 解讀層:結論文字
    ("結論的段號拿確認段", "→ #{RES_TITLE} 第 {IDX_TITLE} 段 →", "→ #{RES_TITLE} 第 {IDX_CONFIRM} 段 →"),
    ("結論把走路聲歸給打字", "是 play_step_sfx 的走路聲", "是 typewriter_tick 的走路聲"),
    ("結論說直接看到", "這是獨立佐證,不是直接看到", "這是直接看到"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s179", MUTANTS))
