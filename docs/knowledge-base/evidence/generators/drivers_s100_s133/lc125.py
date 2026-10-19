# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十五:grant_reward_rows 種類 3 的台詞與 spell_damage_apply 的經驗值累加 —— DOSBox-X 實機。

只對原版 FD2.EXE;只改模擬器記憶體裡的資料(單位記錄、法術列 3 的命中率),程式碼不動。instance 由 LC_INST 指定(預設 lc125)。

用法:
  python lc125.py arm X Y HIT [F7_3]  # 停住:讀 [0x53a79] 文字表並與 FDTXT_001 / 002 比對;敵 #11 搬到 (X, Y)、slot2 = 道具 79;
                                      #   #1..#4 設已行動、索爾清已行動;法術列 3 的命中率 = HIT;F7_3 給了就把 #3 的 +7 改成它;
                                      #   下 ai_item_action 入口與戰敗路徑的斷點;恢復
  python lc125.py rec TAG [秒]        # 逐站記錄(入口停下後才設分支內的斷點);種類 3 每一列在對白等按鍵時截圖
  python lc125.py bpdel | resume
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

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
import decode_text as DT  # noqa: E402

INST = os.environ.get("LC_INST", "lc125")
OUT = Path(__file__).resolve().parent / "cl" / f"{INST}_live"
L = Live(INST, OUT)
VGA, VGA_N = 0xA0000, 64000
FDTXT = {n: REPO / "extracted" / "raw" / "FDTXT" / f"FDTXT_{n:03d}.bin" for n in (1, 2)}

BP_ENTRY = 0x15055      # ai_item_action 入口
BP_EXP_ADD = 0x1C8E2    # spell_damage_apply:add [0x53ec8], eax(eax = 這個目標的經驗值,esi = 目標記錄,edi = 新 HP)
BP_LOOP_END = 0x20FE5   # 逐目標迴圈結束
BP_GRANT = 0x21072      # call grant_reward_rows
BP_K3 = 0x1AC2B         # grant_reward_rows 種類 3:ebx = payload,ebp = 列序
BP_K3_RET = 0x1AC4E     # 種類 3 的 0x15f84 返回
BP_DISP_END = 0x2107A
BP_RET = 0x152FD        # ai_item_action 返回前
STAGE2 = (BP_EXP_ADD, BP_LOOP_END, BP_GRANT, BP_K3, BP_K3_RET, BP_DISP_END, BP_RET)
# ai_item_candidate_select(敵方回合、ai_item_action 之前)
BP_SEL = 0x1567E        # 入口(unit, camp)
BP_SEL_CELLS = 0x1576E  # map_collect_cells_byte3_set 返回:eax = 施放點數,清單 = [esp + 0x34]
BP_SEL_SCORE = 0x157FD  # ai_item_target_score 返回:eax = 分數;[esp] 道具、[esp+4] 筆數、[esp+8] 目標
BP_SEL_END = 0x1586A    # 掃完所有 slot
AISEL = (BP_SEL, BP_SEL_CELLS, BP_SEL_SCORE, BP_SEL_END)
AIM = {"score": 0x53C33, "x": 0x53C37, "y": 0x53C3B, "slot": 0x53C3F}
BP_LOSE = 0x22E5C
BP_TITLE = 0x25EBB
LOSE = (BP_LOSE, BP_TITLE)
SPELL_ROW3_HIT = 0x57A12 + 2   # 法術列 3 在 obj3(執行期 0x1f3a12),+2 是命中率
TXT_TBL = 0x53A79
LBL_TBL = 0x53A7D
EXP = 0x53EC8
# LC_PLACE="5:19:13,10:19:6":#11 第一次進 ai_item_candidate_select 時把這些單位搬到指定格
PLACE = [tuple(int(v) for v in p.split(":")) for p in os.environ.get("LC_PLACE", "").split(",") if p]


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def unit_rows() -> list[dict]:
    n = L.d32(0x53BEB + DELTA) & 0xFF
    b = L.units("units", n)
    rows = []
    for i in range(n):
        r = b[i * 80:(i + 1) * 80]
        hp, mhp = struct.unpack_from("<hh", r, 0x40)
        rows.append({"i": i, "x": r[0], "y": r[1], "f5": r[5], "camp": r[6], "f7": r[7], "cls": r[0x20], "lv": r[0x21],
                     "hp": hp, "mhp": mhp, "reward": r[0x31:0x34].hex()})
    return rows


def bp(addrs: tuple[int, ...]) -> None:
    for a in addrs:
        L.cmd(f"BP 0170:{a + DELTA:x}")


def reset_bps(keep: tuple[int, ...]) -> None:
    L.cmd("BPDEL *")
    bp(keep)


def stack(r: dict[str, int], n: int) -> tuple[int, ...]:
    return struct.unpack(f"<{n}I", L.dump(r["ESP"], 4 * n, "stk"))


def file_strings() -> dict[int, list[list[int]]]:
    return {n: DT.parse_strings(str(p)) for n, p in FDTXT.items()}


def table_check(name: str) -> dict:
    """讀 [0x53a79] 指向的文字緩衝區,與 FDTXT_001 / 002 的檔案位元組逐 byte 比對。"""
    ptr = L.d32(TXT_TBL + DELTA)
    out: dict = {"txt_ptr": hex(ptr), "lbl_ptr": hex(L.d32(LBL_TBL + DELTA))}
    for n, p in FDTXT.items():
        fb = p.read_bytes()
        rb = L.dump(ptr, len(fb), f"{name}_txt{n:03d}")
        diff = sum(a != b for a, b in zip(fb, rb))
        out[f"FDTXT_{n:03d}"] = {"bytes": len(fb), "diff_bytes": diff,
                                 "first_diff": next((i for i, (a, b) in enumerate(zip(fb, rb)) if a != b), None)}
    return out


def runtime_string(ptr: int, idx: int) -> tuple[int, list[int]]:
    """與 0x15f84 相同的取法:movsx eax, word [ptr + idx*2];add ptr, eax;讀到 0xFFFF 為止。"""
    off = struct.unpack("<h", L.dump(ptr + idx * 2, 2, "off"))[0]
    raw = L.dump(ptr + off, 400, "str")
    codes = []
    for j in range(0, len(raw) - 1, 2):
        c = struct.unpack_from("<H", raw, j)[0]
        if c == 0xFFFF:
            break
        codes.append(c)
    return off, codes


def rec(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "stops": []}
    seen: set[int] = set()
    if os.environ.get("LC_MIDRUN"):
        # 從 grant_reward_rows 的台詞中途接續(前一個錄製腳本中斷時,斷點仍是第二階段那組)
        seen |= {BP_ENTRY, BP_GRANT}
        log["midrun"] = True
    fs = file_strings()
    t0 = time.time()
    done = False
    k3 = 0
    while time.time() - t0 < max_s:
        r = L.wait_stop(12, poll=0.5)
        if r is None:
            # 台詞等按鍵(種類 3 列之間、或收尾之後)
            if seen & {BP_GRANT} and BP_DISP_END not in seen:
                L.key("Return", 1.0)
                log["stops"].append({"at": "key", "t": round(time.time() - t0, 1), "name": "送 Return(等待中)"})
                print("送 Return")
            continue
        nat = r.get("EIP", 0) - DELTA
        ent: dict = {"at": hex(nat), "t": round(time.time() - t0, 1)}
        if nat in STAGE2 and BP_ENTRY not in seen:
            ent["name"] = "入口之前的停(略過)"
            log["stops"].append(ent)
            print(ent)
            L.resume()
            continue
        seen.add(nat)
        after_shot = None
        if nat == BP_SEL:
            st = stack(r, 3)
            if st[1] == 11 and PLACE and "placed" not in log:
                # 友軍 NPC 在友軍回合會移動;在 #11 評分之前把指定的 NPC 放到固定格(只改單位記錄 +0/+1)
                for ui, x, y in PLACE:
                    L.sm(L.ua(ui, 0), bytes([x, y]))
                log["placed"] = PLACE
                ent["placed"] = PLACE
            ent.update(name="ai_item_candidate_select 入口", ret=hex(st[0] - DELTA), unit=st[1], camp=st[2],
                       map_w=L.d32(0x53AC1 + DELTA), map_h=L.d32(0x53AC5 + DELTA), units=unit_rows(),
                       inv=L.dump(L.ua(st[1], 0xB), 16, "inv").hex() if st[1] < 64 else None)
        elif nat == BP_SEL_CELLS:
            n = r["EAX"]
            lst = L.d32(r["ESP"] + 0x34)
            cells = L.dump(lst, 2 * n, "cells") if 0 < n < 200 else b""
            ent.update(name="施放點清單", count=n, cells=[[cells[2 * i], cells[2 * i + 1]] for i in range(len(cells) // 2)])
        elif nat == BP_SEL_SCORE:
            st = stack(r, 3)
            cnt = st[1]
            sp = r["ESP"] + 0xC
            ent.update(name="ai_item_target_score 返回", score=s32(r["EAX"]), item=st[0], count=cnt,
                       targets=list(L.dump(st[2], cnt, "tg")) if 0 < cnt < 64 else [],
                       cast=[L.d32(sp + 0x40), L.d32(sp + 0x44)], slot=L.d32(sp + 0x3C),
                       best_before={k: s32(L.d32(a + DELTA)) for k, a in AIM.items()})
        elif nat == BP_SEL_END:
            ent.update(name="ai_item_candidate_select 掃完", best={k: s32(L.d32(a + DELTA)) for k, a in AIM.items()})
        elif nat == BP_ENTRY:
            st = stack(r, 3)
            ent.update(name="ai_item_action 入口", ret=hex(st[0] - DELTA), unit=st[1], camp=st[2],
                       exp=s32(L.d32(EXP + DELTA)), units=unit_rows(), table=table_check(f"{tag}_entry"),
                       hit_row3=L.dump(SPELL_ROW3_HIT - 2 + DELTA, 7, "row3").hex())
            reset_bps(STAGE2 + LOSE)
        elif nat == BP_EXP_ADD:
            ui = (r["ESI"] - L.ubase) // 80
            ent.update(name="經驗值累加之前", eax_add=s32(r["EAX"]), unit=ui, edi_new_hp=r["EDI"], ebp_damage=s32(r["EBP"]),
                       exp_before=s32(L.d32(EXP + DELTA)), row=next(u for u in unit_rows() if u["i"] == ui))
        elif nat == BP_LOOP_END:
            ent.update(name="逐目標迴圈結束", exp=s32(L.d32(EXP + DELTA)), units=unit_rows())
        elif nat == BP_GRANT:
            st = stack(r, 3)
            ent.update(name="call grant_reward_rows", args=[st[0], st[1], hex(st[2])], rows=L.dump(st[2], 12, "rw").hex())
        elif nat == BP_K3:
            ptr = L.d32(TXT_TBL + DELTA)
            pay = r["EBX"] & 0xFFFF
            off, codes = runtime_string(ptr, pay)
            match = {f"FDTXT_{n:03d}": (pay < len(s) and s[pay] == codes) for n, s in fs.items()}
            ent.update(name="種類 3:呼叫 0x15f84 之前", payload=pay, row_index=r["EBP"], unit=r["EDI"], txt_ptr=hex(ptr),
                       str_off=off, codes=codes, file_match=match,
                       file_strings={f"FDTXT_{n:03d}": len(s) for n, s in fs.items()})
            k3 += 1
            after_shot = f"{tag}_k3_{k3}"
        elif nat == BP_K3_RET:
            ent.update(name="種類 3:0x15f84 返回", eax=s32(r["EAX"]))
        elif nat == BP_DISP_END:
            ent.update(name="item_effect_dispatch 收尾", exp=s32(L.d32(EXP + DELTA)), units=unit_rows())
        elif nat == BP_RET:
            ent.update(name="ai_item_action 返回前", exp=s32(L.d32(EXP + DELTA)))
        elif nat in LOSE:
            ent.update(name="戰敗路徑", ret=hex(stack(r, 1)[0] - DELTA))
        else:
            ent.update(name="不是設的斷點", regs={k: hex(v) for k, v in r.items()})
            log["stops"].append(ent)
            print(ent)
            break
        log["stops"].append(ent)
        (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print({k: v for k, v in ent.items() if k not in ("units", "codes", "row")})
        if nat == BP_RET:
            reset_bps(LOSE)
            done = True
            L.resume()
            break
        L.resume()
        if after_shot:
            # 0x15f84 逐字顯示完、等按鍵時截圖並傾印畫面(此時沒有停在斷點)
            time.sleep(6)
            # 注意:執行中不能傾印記憶體(mem dump 要在除錯器裡),只截圖
            running = L.running()
            L.shot(after_shot)
            log["stops"].append({"at": "shot", "t": round(time.time() - t0, 1), "name": after_shot, "running": running})
            print("shot", after_shot, "running", running)
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("stops", len(log["stops"]), "done", done)
    return 0 if done else 1


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "bpdel":
        reset_bps(())
    elif cmd == "rec":
        L.ubase = L.ubase or int((OUT / "ubase.txt").read_text())
        return rec(argv[1], float(argv[2]) if len(argv) > 2 else 600)
    elif cmd in ("units", "arm"):
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        (OUT / "ubase.txt").write_text(str(L.ubase))
        try:
            print("table", json.dumps(table_check("arm"), ensure_ascii=False))
            if cmd == "arm":
                x, y, hit = int(argv[1]), int(argv[2]), int(argv[3])
                L.sm(L.ua(11, 0xE), bytes([0x00, 79]))
                L.sm(L.ua(11, 0), bytes([x, y]))
                L.sm(L.ua(0, 5), bytes([0]))
                for i in (1, 2, 3, 4):
                    L.sm(L.ua(i, 5), bytes([0x80]))
                if len(argv) > 4:
                    L.sm(L.ua(3, 7), bytes([int(argv[4], 0)]))
                u0 = L.dump(L.ua(0, 0), 2, "u0xy")
                L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
                L.sm(SPELL_ROW3_HIT + DELTA, bytes([hit]))
                print("row3", L.dump(SPELL_ROW3_HIT - 2 + DELTA, 7, "row3").hex())
                reset_bps((BP_ENTRY,) + AISEL + LOSE)
                time.sleep(0.5)
            for u in unit_rows():
                print(u)
        finally:
            L.resume()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
