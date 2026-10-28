# 存檔:原 scratchpad 驅動腳本(續一百五十九),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十九第 5 項(實機,使用者 2026-10-28「第五項 核准授權你重新實機重跑驗證」):GAME OVER 回標題後,
清對話迴圈的第幾次 Return 選了新遊戲,以及 delay 的校準。預測見 pred159_item5.txt(量之前寫)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;只改模擬器記憶體(索爾 +5 的 bit0),程式碼不動,
遊戲途中不下斷點。entries / launch / post / pull 沿用 ret157b.py。

用法:
  python ret157b.py entries ; python ret157b.py launch NAME ; python lc157.py hud NAME
  python ret159.py prompt NAME     # 找空格 → 開指令環 → END → 停在「結束這回合?」;截圖
  python ret159.py kill NAME       # 停住、索爾 +5 |= 1、讀回比對、確認沒有斷點、恢復
  python ret159.py go NAME [N]     # Return(YES)+ 清對話迴圈 N 次(預設 45,不提早結束),逐次記主機時間
  python ret157b.py post NAME ; python ret157b.py pull NAME
"""
from __future__ import annotations

import json
import struct
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
OD = REPO / ".wsl_build" / "lc159_live"
SOL_FLAGS = 0x05  # 單位 +5:bit0 = 死亡標記(0x205be 讀 record0 這一位)


def main(argv: list[str]) -> int:
    cmd, name = argv[0], argv[1]
    OD.mkdir(parents=True, exist_ok=True)
    import fd2_chapter_sweep as sw  # noqa: E402

    if cmd == "prompt":
        d = OD / name / "prompt"
        d.mkdir(parents=True, exist_ok=True)
        log: list[str] = []
        found, _ = sw.find_empty_adjacent_tile(name, d, log)
        print("\n".join(log))
        if not found:  # 找不到空格就不開指令環(會選到單位)
            print("沒有確認的空格,停止")
            return 1
        sw.send_keys(name, "Return")
        time.sleep(0.6)
        sw.send_keys(name, "Down")
        time.sleep(0.4)
        sw.send_keys(name, "Return")
        time.sleep(1.5)
        print(sw.screenshot(name, d / "end_turn_prompt.png"))
        return 0

    if cmd == "go":
        n = int(argv[2]) if len(argv) > 2 else 45
        shots = OD / name / "loop"
        shots.mkdir(parents=True, exist_ok=True)
        assert not any(shots.iterdir()), f"{shots} 不是空的"
        rec: list[dict] = []

        def send(key: str, tag: str) -> None:
            t0 = time.time()
            sw.send_keys(name, key)
            rec.append({"op": "send", "key": key, "tag": tag, "t0": t0, "t1": time.time()})

        t_start = time.time()
        send("Return", "yes")
        for k in range(1, n + 1):  # lc131a 的清對話迴圈本體:Return、等 0.6 秒、截圖、cursor_tile_is_empty
            send("Return", f"clear{k:03d}")
            time.sleep(0.6)
            png = shots / f"findempty_clear_{k:03d}.png"
            t0 = time.time()
            sw.screenshot(name, png)
            t1 = time.time()
            state = sw.cursor_tile_is_empty(png)
            rec.append({"op": "shot", "png": png.name, "t0": t0, "t1": t1, "state": state, "t2": time.time()})
        out = {"t_start": t_start, "t_end": time.time(), "n": n, "events": rec}
        (OD / f"{name}_loop.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print("sends", sum(e["op"] == "send" for e in rec), "shots", sum(e["op"] == "shot" for e in rec),
              "elapsed", round(out["t_end"] - t_start, 1))
        return 0

    from live import Live  # noqa: E402
    from ret157b import rd  # noqa: E402
    L = Live(name, HERE / "cl" / f"{name}_live")
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    try:
        if cmd == "kill":
            a = L.ua(0, SOL_FLAGS)
            b0 = rd(L, a, 1, "sol5_before")
            assert b0 is not None, "讀不到索爾 +5"
            L.sm(a, bytes([b0[0] | 1]))
            b1 = rd(L, a, 1, "sol5_after")
            assert b1 is not None and b1[0] == b0[0] | 1, (b0, b1)
            hp = rd(L, L.ua(0, 0x40), 4, "solhp")
            L.cmd("BPLIST")
            time.sleep(0.5)
            bps = [x for x in L.pane().splitlines() if "BP " in x and "BPLIST" not in x]
            res = {"sol_plus5_before": b0[0], "sol_plus5_after": b1[0],
                   "sol_hp": list(struct.unpack("<hh", hp)) if hp else None, "bps": bps, "t_host": time.time()}
            (OD / f"{name}_kill.json").write_text(json.dumps(res), encoding="utf-8")
            print(res)
    finally:
        L.resume()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
