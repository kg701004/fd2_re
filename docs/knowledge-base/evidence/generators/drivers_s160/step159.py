# 存檔:原 scratchpad 驅動腳本(續一百六十),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十九第 5 項第 6 次(實機,使用者 2026-10-28 再次核准「第五項 核准授權你重新實機重跑驗證」):逐鍵送、逐鍵截圖。
第 5 次在 prompt 步驟一次送 Return / Down / Return、只截最後一張,分不出哪一鍵讓索爾移動;這次每呼叫一次只送一個鍵,
截圖並記 cursor_tile_is_empty 與主機時間,看過截圖再決定下一鍵(不符就停)。只對原版 FD2.EXE、WSL -d Ubuntu。

用法:
  python step159.py shot NAME TAG          # 不送鍵,只截圖
  python step159.py key NAME KEY TAG [S]   # 送一個鍵,等 S 秒(預設 0.8),截圖
紀錄:.wsl_build/lc159_live/NAME/steps/NNN_TAG.png 與 NAME_steps.jsonl(每行一步)。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
OD = REPO / ".wsl_build" / "lc159_live"


def main(argv: list[str]) -> int:
    import fd2_chapter_sweep as sw  # noqa: E402

    cmd, name, rest = argv[0], argv[1], argv[2:]
    if cmd == "clear":  # 逐次 Return(每次一步),第一張看到戰場 HUD 就停,不多送
        for _ in range(int(rest[0]) if rest else 40):
            if main(["key", name, "Return", "clear", "0.9"]) != 0:
                return 1
            jl = OD / f"{name}_steps.jsonl"
            last = json.loads(jl.read_text(encoding="utf-8").splitlines()[-1])
            if sw.screen_shows_battle_hud(OD / name / "steps" / last["png"]):
                print("HUD", last["png"])
                return 0
        print("HUD 沒出現")
        return 1
    d = OD / name / "steps"
    d.mkdir(parents=True, exist_ok=True)
    jl = OD / f"{name}_steps.jsonl"
    n = sum(1 for _ in jl.open(encoding="utf-8")) if jl.exists() else 0
    rec: dict = {"n": n, "cmd": cmd}
    if cmd == "key":
        key, tag = rest[0], rest[1]
        wait = float(rest[2]) if len(rest) > 2 else 0.8
        rec.update(key=key, wait=wait, t0=time.time())
        sw.send_keys(name, key)
        rec["t1"] = time.time()
        time.sleep(wait)
    elif cmd == "shot":
        tag = rest[0]
    else:
        print("未知指令", cmd)
        return 2
    png = d / f"{n:03d}_{tag}.png"
    rec["ts0"] = time.time()
    sw.screenshot(name, png)
    rec["ts1"] = time.time()
    if not png.exists():  # 截圖失敗不能當成畫面沒變
        print("截圖失敗", png)
        return 1
    rec.update(png=png.name, empty=sw.cursor_tile_is_empty(png))
    with jl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(rec)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
