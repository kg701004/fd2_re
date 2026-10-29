# 存檔:原 scratchpad 驅動腳本(續一百六十八),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""對 fd2_chapter_sweep.py 新增的面板判準 / 送鍵閘門做變異:每個變異都必須讓 --selftest 印出 SELFTEST FAILED。
變異版放在暫存目錄(連同 fd2save.py 等同目錄模組),不改 repo 內的檔案。"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
TOOLS = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
SRC = (TOOLS / "fd2_chapter_sweep.py").read_text(encoding="utf-8")

MUTANTS = [
    ("門檻改成 >", "_flat_blue_fraction(im, r) >= DIALOGUE_PANEL_FLAT_MIN", "_flat_blue_fraction(im, r) > DIALOGUE_PANEL_FLAT_MIN"),
    ("不檢查最多色是否 HUD 藍", "return n / sum(counts.values()) if _is_hud_blue(color) else 0.0", "return n / sum(counts.values())"),
    ("只看下帶", "for r in DIALOGUE_PANEL_BANDS)", "for r in DIALOGUE_PANEL_BANDS[1:])"),
    ("用藍色總比例而非單色", "color, n = max(counts.items(), key=lambda kv: kv[1])",
     "color, n = max(counts.items(), key=lambda kv: kv[1]); n = sum(v for c, v in counts.items() if _is_hud_blue(c))"),
    ("panel_gate 不擋", "        if not screen_shows_dialogue_panel(last):\n            t0 = time.time()",
     "        if False:\n            t0 = time.time()"),
    ("等待中面板出現不跳出", "                if screen_shows_dialogue_panel(last):\n                    break",
     "                if False:\n                    break"),
    ("不問 control_probe", "if control_probe is not None and control_probe():", "if False:"),
    ("等待中 HUD 出現不結束", "                if screen_shows_battle_hud(last):\n                    log.append(f\"[{tag}] battle HUD recovered after {pressed} clear-Return(s), \"",
     "                if False:\n                    log.append(f\"[{tag}] battle HUD recovered after {pressed} clear-Return(s), \""),
    ("指令環逾時照樣往下", "                return {\"ok\": False, \"stage\": \"ring\", \"t_host\": t_host}",
     "                break"),
    ("不檢查確認框", "    if not screen_shows_dialogue_panel(prompt):", "    if False:"),
    ("找不到空格照樣開環", "    found, _ = find_empty_adjacent_tile(name, shots_dir, log)\n    if not found:\n        log.append(\"send_end_turn_keys",
     "    found, _ = find_empty_adjacent_tile(name, shots_dir, log)\n    if False:\n        log.append(\"send_end_turn_keys"),
    ("預設改成 panel_gate", "panel_gate: bool = False, settle_s", "panel_gate: bool = True, settle_s"),
]

killed = 0
with tempfile.TemporaryDirectory() as root:
    # 模組用 Path(__file__).parent.parent 找 docs/data/chapter_beats,暫存目錄要照同樣的結構擺
    td = str(Path(root) / "tools")
    Path(td).mkdir()
    shutil.copytree(TOOLS.parent / "docs" / "data" / "chapter_beats", Path(root) / "docs" / "data" / "chapter_beats")
    for f in TOOLS.glob("*.py"):
        shutil.copy(f, td)
    for label, old, new in MUTANTS:
        n = SRC.count(old)
        if n != 1:
            print(f"BAD PATTERN ({n}x): {label}")
            continue
        (Path(td) / "fd2_chapter_sweep.py").write_text(SRC.replace(old, new), encoding="utf-8", newline="\n")
        r = subprocess.run([sys.executable, "-W", "ignore", str(Path(td) / "fd2_chapter_sweep.py"), "--selftest"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=td, timeout=300)
        out = r.stdout + r.stderr
        ok = r.returncode != 0 and "SELFTEST FAILED" in out and "Traceback" not in out
        killed += ok
        print(f"{'KILLED' if ok else 'SURVIVED'}: {label} (rc={r.returncode}{', Traceback' if 'Traceback' in out else ''})")
print(f"{killed}/{len(MUTANTS)} killed")
sys.exit(0 if killed == len(MUTANTS) else 1)
