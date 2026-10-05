# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續六十五:用 fd2_chapter_sweep 的前半段(改章節存檔 → LOAD → attempt_camp_exit → ensure_battle_hud)
進到第 N 章的戰場就停下,不做 mass-kill / End-Turn,也不 teardown,留給後續手動傾印與受控攻擊。

用法:python reach_battle.py <chapter> <instance> <source.SAV> <out_dir>
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
import fd2_chapter_sweep as sw  # noqa: E402


def _mean(p: Path, box: tuple[int, int, int, int]) -> tuple:
    from PIL import Image
    return Image.open(p).convert("RGB").crop(box).resize((1, 1)).getpixel((0, 0))


def is_title(p: Path) -> bool:
    """標題選單:火焰標誌區平均偏橘、副標橫幅偏藍(v22 實測 logo (200,161,88)、banner (69,96,141))。"""
    r, g, b = _mean(p, (300, 330, 760, 450))
    br, bg, bb = _mean(p, (380, 492, 660, 512))
    return r > 150 and g > 110 and b < 130 and bb > br + 30


def is_black(p: Path) -> bool:
    from PIL import Image
    return max(max(c) for c in Image.open(p).convert("RGB").resize((32, 24)).getdata()) < 12


def main() -> int:
    n, name, src, out = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    patched = out / "patched.SAV"
    # 出戰人數格狀選人畫面的章節要 roster_cap = 門檻 + 1(doc99 round_ch2528)
    cap = sw.guard_selection_threshold(n) + 1 if n in sw.ROSTER_PICK_GRID_CHAPTERS else None
    sw.prepare_chapter_save(src, n, patched, 0, log, pad_roster=True, roster_mode="complete", roster_cap=cap)
    roster = len(sw.complete_roster_ids(n, cap=cap))
    sw.launch_instance(name, keepalive=7200)
    time.sleep(12)
    sw.overwrite_save(name, patched)
    # 續七十五:原本固定 30 次 Escape 後盲送 Down / Return —— 開機稍慢時按鍵落在開場或 START,
    # 開成新遊戲(v23~v27 連續五次)。改成截圖確認標題選單(火焰標誌 + 藍色副標)出現才選 LOAD。
    for i in range(60):
        sw.send_keys(name, "Escape")
        time.sleep(1.0)
        if i % 3 == 2 and is_title(sw.screenshot(name, shots / "01_title_wait.png")):
            break
    else:
        raise SystemExit("title menu never appeared (01_title_wait.png)")
    log.append(f"reach: title menu seen after {i + 1} Escape(s)")
    sw.send_keys(name, "Down")
    time.sleep(0.5)
    sw.send_keys(name, "Return")
    time.sleep(2.0)
    sw.send_keys(name, "Return")
    time.sleep(2.5)
    if is_black(sw.screenshot(name, shots / "02_post_load.png")):
        time.sleep(3.0)
        if is_black(sw.screenshot(name, shots / "02_post_load.png")):
            raise SystemExit("post-load screen is black: LOAD did not take (02_post_load.png)")
    adv = sw.attempt_camp_exit(name, shots, log, dialogue_steps=sw.CAMP_EXIT_DIALOGUE_STEPS.get(n, 120),
                               chapter_n=n, roster_count=roster)
    base = adv["battle_base"] if adv else None
    hud = sw.ensure_battle_hud(name, shots, log, "reach") if base is not None else (False, 0)
    res = {"chapter": n, "instance": name, "battle_base": base, "hud": hud, "roster_count": roster}
    (out / "reach.json").write_text(json.dumps({"result": res, "log": log}, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print(json.dumps(res))
    for line in log[-12:]:
        print(" ", line[:200])
    return 0 if base is not None and hud[0] else 1


if __name__ == "__main__":
    sys.exit(main())
