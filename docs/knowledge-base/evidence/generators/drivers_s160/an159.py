# 存檔:原 scratchpad 驅動腳本(續一百六十),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十九第 5 項第 6 次(lc159b)的離線解析(唯讀):列出送鍵(主機時間)、有鍵事件群(模擬時間)、讀鍵 / 清鍵 / 標題序列事件。
用法:python an159.py <過濾後的呼叫紀錄> <loop.json>"""
from __future__ import annotations

import json
import sys

DELTA = 0x19C000
NAMES = {0x22E5C: "GAMEOVER", 0x1F894: "title", 0x1FC66: "intro_exit", 0x1FD7C: "menu_flush", 0x370F0: "readkey",
         0x1FE63: "menu_key", 0x1FED3: "confirm", 0x1FEF0: "blink", 0x1FF31: "fade", 0x1FF36: "cls",
         0x32326: "newgame", 0x4E381: "kbd_flush"}


def parse(path: str) -> list[dict]:
    out = []
    for line in open(path, encoding="ascii", errors="replace"):
        t = line.split()
        if not t or t[0] not in ("E", "R"):
            continue
        d = {"k": t[0], "seq": int(t[1]), "eip": int(t[2], 16) - DELTA}
        if t[0] == "R":
            d["eax"] = int(t[3], 16)
        for x in t:
            if x[:2] in ("i=", "n=", "t="):
                d[x[0]] = float(x[2:])
        out.append(d)
    return out


def main(log: str, loopj: str) -> None:
    recs = parse(log)
    lp = json.load(open(loopj, encoding="utf-8"))
    sends = [e for e in lp["events"] if e["op"] == "send"]
    # 有鍵群:has_key 回非 0 的 R 記錄,相隔 > 50 ms 視為新的一群
    hk = [r for r in recs if r["k"] == "R" and r["eip"] == 0x10620]
    groups: list[list[dict]] = []
    for r in hk:
        if groups and r["t"] - groups[-1][-1]["t"] <= 50:
            groups[-1].append(r)
        else:
            groups.append([r])
    print("sends", len(sends), "has_key 群", len(groups))
    ev = [(r["t"], NAMES.get(r["eip"], hex(r["eip"])), r["seq"]) for r in recs
          if r["k"] == "E" and r["eip"] in NAMES]
    ev += [(g[0]["t"], f"KEY+ ({len(g)} polls, until {g[-1]['t']:.1f})", g[0]["seq"]) for g in groups]
    ev.sort()
    t_go = ev[0][0]
    for t, nm, seq in ev:
        print(f"{(t - t_go) / 1000:9.3f}  seq {seq:5d}  {nm}")
    h0 = sends[0]["t0"]
    print("host sends (s, rel YES):", [round(s["t0"] - h0, 2) for s in sends])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
