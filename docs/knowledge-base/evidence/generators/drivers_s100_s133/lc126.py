# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十六:章節索引 22 的戰後處理器 0x24754 裡三次 lut_circle_ramp_at_unit,以及每幀停留多久 —— DOSBox-X 實機。

只對原版 FD2.EXE;只改模擬器記憶體裡的資料([0x53ecc] 結果碼、[0x53c03] 章節索引),程式碼不動。
在第 1 章戰場(章節位元組 1)觸發:玩家階段迴圈的檢查點 0x1d8aa 把 [0x53ecc] 寫成 2(勝利),
戰役迴圈 0x25e1e 讀章節索引之前寫成 22,於是 0x25e23 call [0x51de9 + 22*4] = 0x24754。
計時讀 BIOS tick(線性 0x46c,約 54.9 ms 一個);停在除錯器時模擬器不跑,所以 tick 是模擬時間(cycles 固定 5000)。

用法:
  python lc126.py arm            # 停住、記 ubase、下 0x1d8aa;恢復
  python lc126.py rec TAG [秒]   # 逐站記錄;第 1 次 lut 呼叫逐幀停(傾印畫面),第 2、3 次只停入口與返回
  python lc126.py bpdel | resume | tick
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live  # noqa: E402

INST = os.environ.get("LC_INST", "lc126")
OUT = Path(__file__).resolve().parent / "cl" / f"{INST}_live"
L = Live(INST, OUT)
VGA, VGA_N = 0xA0000, 64000
TICK = 0x46C            # BIOS tick 計數(線性,不加 DELTA)

BP_PHASE_CHECK = 0x1D8AA   # 玩家階段迴圈:cmp [0x53ecc], 0
BP_OUTER_CHECK = 0x1A4F5   # 階段之間:cmp [0x53ecc], 0
# 寫入點:玩家階段迴圈與三個階段之間的檢查(0x1a599 由 fixup 0x1a59b 回推的指令開頭)
WRITE_ECC = (BP_PHASE_CHECK, 0x1A4F5, 0x1A566, 0x1A599)
BP_CAMPAIGN = 0x25DD5      # 戰役迴圈:battle_main_input_loop 返回後
BP_POST = 0x25E1E          # 讀 [0x53c03] 之前
BP_H_ENTRY = 0x24754
BP_DLG14 = 0x2495D         # inc [0x53c03] 之後、dialog 14 之前
# (位址, 名稱):delay / lut / flicker 的前後
SEQ = {
    0x24965: "delay(400) #1 之前", 0x2496F: "delay(400) #1 返回",
    0x24978: "call lut #1", 0x2497D: "lut #1 返回",
    0x24980: "call flicker #1", 0x24987: "flicker #1 返回",
    0x249B1: "delay(400) #2 之前", 0x249BB: "delay(400) #2 返回",
    0x249C4: "call lut #2", 0x249C9: "lut #2 返回",
    0x249CC: "call flicker #2", 0x249D3: "flicker #2 返回",
    0x249FD: "delay(400) #3 之前", 0x24A07: "delay(400) #3 返回",
    0x24A10: "call lut #3", 0x24A15: "lut #3 返回",
    0x24A3E: "調色盤迴圈結束",
    0x25E2A: "0x24754 返回",
    # 第二次:處理器前半每個呼叫點(定位第一次在哪裡當掉)
    0x247B4: "call layout_units", 0x247BE: "call party_has_item(100)", 0x247EA: "call dialog 8", 0x247F4: "call join(22)",
    0x2481A: "call dialog 9", 0x2482E: "call act(71)", 0x24838: "call roster_has(13)", 0x24863: "call dialog 10",
    0x24877: "call act(72) a", 0x24881: "call deactivate(17) a", 0x248A8: "call dialog 11", 0x248DD: "call dialog 12",
    0x248F1: "call act(72) b", 0x248FB: "call deactivate(17) b", 0x24921: "call dialog 13", 0x2492B: "call join(19)",
    0x24933: "call sync_party", 0x24962: "dialog 14 返回",
}
BP_LUT = 0x2189A
BP_FRAME = 0x2198E          # 每幀 copy_rect 之後:ebx = 幀序號,esi = 半徑
STAGE = (BP_H_ENTRY, BP_DLG14, BP_LUT, BP_FRAME) + tuple(SEQ)
G = {"ecc": 0x53ECC, "chap": 0x53C03, "scroll_x": 0x53AA9, "scroll_y": 0x53AAD, "turn": 0x53BEF}


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def bp(addrs: tuple[int, ...]) -> None:
    for a in addrs:
        L.cmd(f"BP 0170:{a + DELTA:x}")


def reset_bps(keep: tuple[int, ...]) -> None:
    L.cmd("BPDEL *")
    bp(keep)


def stack(r: dict[str, int], n: int) -> tuple[int, ...]:
    return struct.unpack(f"<{n}I", L.dump(r["ESP"], 4 * n, "stk"))


def tick() -> int:
    return L.d32(TICK)


def glob() -> dict[str, int]:
    return {k: s32(L.d32(a + DELTA)) for k, a in G.items()}


def unit(i: int) -> dict:
    r = L.dump(L.ua(i, 0), 80, "u")
    return {"i": i, "x": r[0], "y": r[1], "f5": r[5], "camp": r[6], "hp": struct.unpack_from("<h", r, 0x40)[0]}


def rec(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "stops": []}
    seen: list[int] = []
    t0 = time.time()
    lut_n = 0
    done = False
    while time.time() - t0 < max_s:
        r = L.wait_stop(12, poll=0.5)
        if r is None:
            # 對白等按鍵(戰後處理器裡的 dialog);進處理器之前不送鍵
            if BP_H_ENTRY in seen:
                L.key("Return", 1.0)
                n_key = sum(1 for s in log["stops"] if s.get("at") == "key") + 1
                L.shot(f"{tag}_key{n_key:02d}")
                log["stops"].append({"at": "key", "t": round(time.time() - t0, 1), "name": "送 Return(等待中)",
                                     "shot": f"{tag}_key{n_key:02d}"})
                print("送 Return")
            continue
        if not r:
            # pane 不是 Running 也沒有暫存器:多半是模擬器結束了,記下 pane 最後幾行
            tail = [x for x in L.pane().splitlines() if x.strip()][-4:]
            log["stops"].append({"at": "exit", "t": round(time.time() - t0, 1), "pane": tail})
            print("模擬器沒有停在除錯器", tail)
            break
        nat = r.get("EIP", 0) - DELTA
        ent: dict = {"at": hex(nat), "t": round(time.time() - t0, 1), "tick": tick()}
        seen.append(nat)
        dump_vga = None
        if nat in WRITE_ECC and "ecc_written" not in log:
            before = glob()
            L.sm(G["ecc"] + DELTA, struct.pack("<i", 2))
            log["ecc_written"] = hex(nat)
            ent.update(name="結果碼檢查:[0x53ecc] 寫成 2", before=before, after=glob(), u0=unit(0), u1=unit(1))
            reset_bps((BP_CAMPAIGN, BP_POST) + STAGE)
        elif nat == BP_CAMPAIGN:
            ent.update(name="戰役迴圈", g=glob())
        elif nat == BP_POST:
            before = glob()
            L.sm(G["chap"] + DELTA, struct.pack("<i", 22))
            tbl = L.d32(0x51DE9 + 22 * 4 + DELTA)
            ent.update(name="戰後表之前:[0x53c03] 寫成 22", before=before, after=glob(), table_22=hex(tbl - DELTA))
        elif nat == BP_H_ENTRY:
            st = stack(r, 1)
            ent.update(name="0x24754 入口", ret=hex(st[0] - DELTA), g=glob(), u1=unit(1),
                       count=L.d32(0x53BEB + DELTA) & 0xFF)
        elif nat == BP_DLG14:
            st = stack(r, 2)
            ent.update(name="dialog 14 之前(inc 之後)", g=glob(), dialog_idx=st[1])
            dump_vga = f"{tag}_dlg14"
        elif nat == BP_LUT:
            lut_n += 1
            st = stack(r, 4)
            ent.update(name=f"lut_circle_ramp_at_unit 入口 #{lut_n}", ret=hex(st[0] - DELTA), args=[s32(v) for v in st[1:]],
                       u=unit(st[1]) if st[1] < 64 else None, g=glob())
            if lut_n > 1:
                # 第 2、3 次不逐幀停:拿掉每幀斷點,和第 1 次比,看斷點本身有沒有影響計時
                L.cmd(f"BPDEL *")
                bp((BP_CAMPAIGN, BP_POST) + tuple(a for a in STAGE if a != BP_FRAME))
        elif nat == BP_FRAME:
            ent.update(name=f"lut #{lut_n} 幀", frame=r["EBX"], radius=s32(r["ESI"]))
            dump_vga = f"{tag}_lut{lut_n}_f{r['EBX']}"
        elif nat in SEQ:
            ent.update(name=SEQ[nat], g=glob())
            dump_vga = f"{tag}_seq_{nat:x}"
        else:
            ent.update(name="不是設的斷點", regs={k: hex(v) for k, v in r.items()})
            log["stops"].append(ent)
            print(ent)
            break
        if dump_vga:
            L.dump(VGA, VGA_N, dump_vga)
            ent["vga"] = dump_vga
        if nat in (BP_LUT, BP_FRAME, BP_H_ENTRY) and "palette" not in log:
            pal = L.d32(0x53A65 + DELTA)
            log["palette"] = L.dump(pal, 768, f"{tag}_pal").hex()
        log["stops"].append(ent)
        (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print({k: v for k, v in ent.items() if k not in ("u0",)})
        if nat == 0x25E2A:
            reset_bps(())
            done = True
            L.resume()
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("stops", len(log["stops"]), "done", done)
    return 0 if done else 1


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "bpdel":
        reset_bps(())
    elif cmd == "tick":
        # 對照:執行中隔幾秒讀兩次 tick,確認 0x46c 是在走的 BIOS tick(要停住才讀得到)
        out = []
        for _ in range(2):
            if not L.halt():
                print("停不進遊戲內容")
                return 1
            out.append((time.time(), tick()))
            L.resume()
            time.sleep(5)
        (dt, dk) = (out[1][0] - out[0][0], out[1][1] - out[0][1])
        print("real s", round(dt, 2), "ticks", dk, "ticks/s", round(dk / dt, 2))
    elif cmd == "rec":
        L.ubase = L.ubase or int((OUT / "ubase.txt").read_text())
        return rec(argv[1], float(argv[2]) if len(argv) > 2 else 900)
    elif cmd == "arm":
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        (OUT / "ubase.txt").write_text(str(L.ubase))
        try:
            print("g", glob(), "count", L.d32(0x53BEB + DELTA) & 0xFF, "u0", unit(0), "u1", unit(1))
            print("table_22", hex(L.d32(0x51DE9 + 22 * 4 + DELTA) - DELTA))
            reset_bps(WRITE_ECC)
            time.sleep(0.5)
        finally:
            L.resume()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
