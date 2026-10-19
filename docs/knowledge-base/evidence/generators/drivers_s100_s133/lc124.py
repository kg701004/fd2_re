# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十四:(1) 玩家「休息」的 rest_hp_recover;(2) item_effect_dispatch 的 0x14 / 0x18 分支內部 —— DOSBox-X 實機。

只對原版 FD2.EXE;只改模擬器記憶體裡的資料(單位記錄、法術列的命中率),程式碼不動。instance 由 LC_INST 指定(預設 lc124)。

用法:
  python lc124.py units
  python lc124.py arm S_HP X Y [HIT]   # 停住:敵 #11 搬到 (X, Y)、slot2 = 道具 79;索爾 HP = S_HP(-1 不動);
                                       #   #1..#4 設已行動、索爾清已行動;HIT 給了就改法術列 3 的命中率;
                                       #   下「休息」+ ai_item_action 入口 + 戰敗路徑的斷點;恢復
  python lc124.py rec TAG [秒] [E_HP]  # 逐站記錄;E_HP 給了就在 ai_item_action 入口把索爾 HP 改成 E_HP
  python lc124.py watch TAG [秒]       # 只等戰敗路徑
  python lc124.py bpdel | resume
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

INST = os.environ.get("LC_INST", "lc124")
OUT = Path(__file__).resolve().parent / "cl" / f"{INST}_live"
L = Live(INST, OUT)
VGA, VGA_N = 0xA0000, 64000

# 玩家指令環的休息
BP_RING = 0x19077       # 指令不是 0 / 1 / 2 的那一支:cmp [esp + 0xa0], 0
BP_REST = 0x13FD4       # rest_hp_recover 入口
BP_RESTW = 0x1410A      # mov [ebx + 0x40], di
BP_RESTRET = 0x19087    # 玩家呼叫點的返回
REST = (BP_RING, BP_REST, BP_RESTW, BP_RESTRET)
BP_ENTRY = 0x15055      # ai_item_action 入口
# item_effect_dispatch 的 0x14 / 0x18 分支
BP_DISP = 0x20C6F
BP_ANIM_CALL = 0x20F80  # call play_map_effect_animation
BP_ANIM_FRAME = 0x1C640  # play_map_effect_animation 每幀 copy_rect 之後(edi = 幀序)
BP_ANIM_RET = 0x20F85
BP_FLASH_CALL = 0x20F9B
BP_FLASH_FRAME = 0x1CD8E  # flash_listed_units_band_cycle 每幀 copy_rect 之後(esi = 幀序)
BP_FLASH_RET = 0x20FA0
BP_RES = 0x1C75E        # spell_damage_resolve 入口
BP_RES_BASE = 0x1C7ED   # 命中亂數之前(esi = 基礎傷害,ebx = 法術列)
BP_RES_ROLL = 0x1C7FE   # edx = rand % 100
BP_RES_MISS = 0x1C816   # 沒命中 / 種族閘門
BP_APPLY = 0x1C81F      # spell_damage_apply 入口
BP_APPLY_ROLL = 0x1C87F  # edx = rand % 100
BP_APPLY_SUB = 0x1C897  # ebp = 傷害,edi = 扣之前的 HP
BP_RES_RET = 0x20FD0
BP_POP_NUM = 0x20FAE    # call queue_unit_number_popup
BP_POP_FIX = 0x20FDB    # call queue_unit_fixed_popup
BP_LOOP_END = 0x20FE5
BP_FIN_FRAME = 0x1DFD7  # action_finish_effect 每幀 copy_rect 之後(ebp = 幀序)
BP_FIN_RET = 0x20FF4
BP_SWEEP = 0x21062      # call unit_death_sweep(ebx = 獎勵列數)
BP_SWEEP_RET = 0x21067
BP_GRANT = 0x21072      # call grant_reward_rows
BP_DISP_END = 0x2107A
BP_POST = 0x152F5       # ai_item_action 內 item_effect_dispatch 的返回
BP_RET = 0x152FD
BRANCH = (BP_DISP, BP_ANIM_CALL, BP_ANIM_FRAME, BP_ANIM_RET, BP_FLASH_CALL, BP_FLASH_FRAME, BP_FLASH_RET, BP_RES,
          BP_RES_BASE, BP_RES_ROLL, BP_RES_MISS, BP_APPLY, BP_APPLY_ROLL, BP_APPLY_SUB, BP_RES_RET, BP_POP_NUM,
          BP_POP_FIX, BP_LOOP_END, BP_FIN_FRAME, BP_FIN_RET, BP_SWEEP, BP_SWEEP_RET, BP_GRANT, BP_DISP_END, BP_POST,
          BP_RET)
BP_LOSE = 0x22E5C
BP_TITLE = 0x25EBB
LOSE = (BP_LOSE, BP_TITLE)
# 法術列 3 的命中率。反組譯上的位址是 0x619fd + 3 * 7 = 0x61a12,但那一段資料的載入位移不是 DELTA:
# 第一輪在 0x1c7ed 讀到 row7_ptr_619fd(3) 的回傳值是線性 0x1f3a12(= 0x57a12 + DELTA),照實際讀到的用。
SPELL_ROW3_HIT = 0x57A12 + 2
G = {"target_x": 0x53C37, "target_y": 0x53C3B, "slot": 0x53C3F, "cursor_x": 0x53AB1, "cursor_y": 0x53AB5,
     "scroll_x": 0x53AA9, "scroll_y": 0x53AAD, "result": 0x53ECC, "popups": 0x53EC4, "exp": 0x53EC8,
     "ring_cmd": 0x53C57, "step_sel": 0x51A83}


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def globs() -> dict[str, int]:
    return {k: s32(L.d32(a + DELTA)) for k, a in G.items()}


def unit_rows() -> list[dict]:
    n = L.d32(0x53BEB + DELTA) & 0xFF
    b = L.units("units", n)
    rows = []
    for i in range(n):
        r = b[i * 80:(i + 1) * 80]
        hp, mhp = struct.unpack_from("<hh", r, 0x40)
        rows.append({"i": i, "x": r[0], "y": r[1], "f5": r[5], "camp": r[6], "f7": r[7], "cls": r[0x20], "lv": r[0x21],
                     "poison": r[0x25], "para": r[0x26], "hp": hp, "mhp": mhp, "inv": r[0xA:0x1A].hex()})
    return rows


def show() -> None:
    print("ubase", hex(L.ubase), globs())
    for r in unit_rows():
        print(f"#{r['i']:2d} x={r['x']:2d} y={r['y']:2d} +5={r['f5']:02x} +6={r['camp']:02x} +7={r['f7']:02x} "
              f"cls={r['cls']} lv={r['lv']} hp={r['hp']}/{r['mhp']} inv={r['inv'][:12]}")


def bp(addrs: tuple[int, ...]) -> None:
    for a in addrs:
        L.cmd(f"BP 0170:{a + DELTA:x}")


def reset_bps(keep: tuple[int, ...]) -> None:
    """BPDEL 只收序號或 *:全部清掉,只留 keep。"""
    L.cmd("BPDEL *")
    bp(keep)


def stack(r: dict[str, int], n: int) -> tuple[int, ...]:
    return struct.unpack(f"<{n}I", L.dump(r["ESP"], 4 * n, "stk"))


def frame(tag: str, kind: str, k: int) -> str:
    name = f"{tag}_{kind}{k:02d}"
    L.dump(VGA, VGA_N, name)
    return name


def rec(tag: str, max_s: float, entry_hp: int | None) -> int:
    log: dict = {"tag": tag, "stops": []}
    seen: set[int] = set()
    t0 = time.time()
    done = False
    quiet = 0
    while time.time() - t0 < max_s:
        r = L.wait_stop(12, poll=0.5)
        if r is None:
            quiet += 1
            # 收尾階段的陣亡台詞要按鍵才會往下走
            if seen & {BP_FIN_RET, BP_SWEEP} and BP_POST not in seen:
                L.key("Return", 1.0)
                log["stops"].append({"at": "key", "t": round(time.time() - t0, 1), "name": "送 Return(等待中)"})
                print("送 Return")
            continue
        quiet = 0
        nat = r.get("EIP", 0) - DELTA
        ent: dict = {"at": hex(nat), "t": round(time.time() - t0, 1)}
        if nat in BRANCH and BP_ENTRY not in seen:
            ent["name"] = "入口之前的停(略過)"
            log["stops"].append(ent)
            print(ent)
            L.resume()
            continue
        seen.add(nat)
        if nat == BP_RING:
            ent.update(name="指令環:不是攻擊 / 法術 / 道具的那一支", unit=r["EBP"], g=globs(),
                       moved_flag=L.d32(r["ESP"] + 0xA0))
        elif nat == BP_REST:
            st = stack(r, 2)
            u = unit_rows()[st[1]] if st[1] < 64 else None
            ent.update(name="rest_hp_recover 入口", ret=hex(st[0] - DELTA), unit=st[1], row=u)
            if st[0] - DELTA != BP_RESTRET:
                ent["note"] = "不是玩家指令環呼叫的;清掉休息的斷點"
                reset_bps((BP_ENTRY,) + LOSE)
        elif nat == BP_RESTW:
            ent.update(name="rest_hp_recover 寫 HP 之前", edi_new_hp=r["EDI"], esi_mhp=r["ESI"], eax_quot=r["EAX"])
        elif nat == BP_RESTRET:
            ent.update(name="rest_hp_recover 返回(玩家)", eax=r["EAX"], g=globs(),
                       units=[u for u in unit_rows() if u["i"] == 0])
            reset_bps((BP_ENTRY,) + LOSE)
        elif nat == BP_ENTRY:
            st = stack(r, 3)
            ent.update(name="ai_item_action 入口", ret=hex(st[0] - DELTA), unit=st[1], camp=st[2], g=globs(),
                       units=unit_rows())
            if entry_hp is not None:
                L.sm(L.ua(0, 0x40), struct.pack("<h", entry_hp))
                ent["set_hero_hp"] = entry_hp
                ent["hero_hp_after_set"] = struct.unpack("<h", L.dump(L.ua(0, 0x40), 2, "hp0"))[0]
            ent["hit_row3"] = L.dump(SPELL_ROW3_HIT - 2 + DELTA, 7, "row3").hex()
            reset_bps(BRANCH + LOSE)
        elif nat == BP_DISP:
            st = stack(r, 5)
            ent.update(name="item_effect_dispatch 入口", ret=hex(st[0] - DELTA), user=st[1], slot=st[2], count=st[3],
                       targets=L.dump(st[4], 8, "disp_targets")[:st[3]].hex(), units=unit_rows())
        elif nat in (BP_ANIM_CALL, BP_FLASH_CALL):
            st = stack(r, 4)
            ent.update(name="call play_map_effect_animation" if nat == BP_ANIM_CALL else "call flash_listed_units_band_cycle",
                       args=[st[0], st[1], st[2], hex(st[3])], targets=L.dump(st[3], 8, "t")[:st[2]].hex(), g=globs())
            if nat == BP_ANIM_CALL:
                ent["tbl_first_frame_1f33"] = L.dump(0x51F33 + DELTA, 33, "t1f33").hex()
                ent["tbl_frame_count_1f54"] = L.dump(0x51F54 + DELTA, 33, "t1f54").hex()
                ent["tbl_sfx_1f75"] = L.dump(0x51F75 + DELTA, 33, "t1f75").hex()
                L.dump(L.d32(0x53A65 + DELTA), 768, f"{tag}_pal")
                frame(tag, "pre", 0)
            else:
                ent["tbl_band_2006"] = L.dump(0x52006 + DELTA, 30, "t2006").hex()
                ent["unit_set_3c0b"] = s32(L.d32(0x53C0B + DELTA))
        elif nat == BP_ANIM_FRAME:
            ent.update(name="動畫幀", k=r["EDI"], anim=r["EBP"], dump=frame(tag, "anim", r["EDI"]))
        elif nat == BP_FLASH_FRAME:
            ent.update(name="閃爍幀", k=r["ESI"], dump=frame(tag, "flash", r["ESI"]))
        elif nat == BP_FIN_FRAME:
            ent.update(name="收尾幀", k=r["EBP"], dump=frame(tag, "fin", r["EBP"]))
        elif nat in (BP_ANIM_RET, BP_FLASH_RET, BP_FIN_RET):
            name = {BP_ANIM_RET: "play_map_effect_animation 返回", BP_FLASH_RET: "flash 返回", BP_FIN_RET: "action_finish_effect 返回"}[nat]
            ent.update(name=name, dump=frame(tag, f"ret{nat:x}_", 0))
            if nat == BP_FIN_RET:
                ent["units"] = unit_rows()
                L.shot(f"{tag}_finret")
        elif nat == BP_RES:
            st = stack(r, 3)
            ent.update(name="spell_damage_resolve 入口", ret=hex(st[0] - DELTA), target=st[1], spell=st[2],
                       row=unit_rows()[st[1]])
        elif nat == BP_RES_BASE:
            ent.update(name="命中亂數之前", esi_base=s32(r["ESI"]), spell_row=L.dump(r["EBX"], 7, "srow").hex(),
                       spell_row_at=hex(r["EBX"] - DELTA), hit=L.d32(r["ESP"] + 0x70),
                       resist_tbl=list(struct.unpack("<28i", L.dump(r["ESP"], 112, "resist"))))
        elif nat == BP_RES_ROLL:
            ent.update(name="命中亂數", edx_roll=s32(r["EDX"]), hit=L.d32(r["ESP"] + 0x70))
        elif nat == BP_RES_MISS:
            ent.update(name="沒命中(回 0)")
        elif nat == BP_APPLY:
            st = stack(r, 3)
            ent.update(name="spell_damage_apply 入口", ret=hex(st[0] - DELTA), target=st[1], base=s32(st[2]))
        elif nat == BP_APPLY_ROLL:
            ent.update(name="傷害亂數", edx_roll=s32(r["EDX"]), ebp_nine_tenths=s32(r["EBP"]), edi_hp=r["EDI"])
        elif nat == BP_APPLY_SUB:
            ent.update(name="扣 HP 之前", ebp_damage=s32(r["EBP"]), edi_hp=r["EDI"])
        elif nat == BP_RES_RET:
            ent.update(name="spell_damage_resolve 返回", eax=s32(r["EAX"]), esi_index=r["ESI"])
        elif nat == BP_POP_NUM:
            st = stack(r, 3)
            ent.update(name="call queue_unit_number_popup", args=[s32(st[0]), st[1], st[2]])
        elif nat == BP_POP_FIX:
            ent.update(name="call queue_unit_fixed_popup", args=[stack(r, 1)[0]])
        elif nat == BP_LOOP_END:
            n = L.d32(0x53EC4 + DELTA)
            ent.update(name="逐目標迴圈結束", popups=n, g=globs(),
                       glyph=L.dump(0x53C6C + DELTA, 40, "q1")[:n].hex(), dx=L.dump(0x53D34 + DELTA, 40, "q2")[:n].hex(),
                       owner=L.dump(0x53DFC + DELTA, 40, "q3")[:n].hex(), units=unit_rows(),
                       tbl_curve_202c=L.dump(0x5202C + DELTA, 25, "t202c").hex(),
                       fmt_501b6=L.dump(0x501B6 + DELTA, 8, "fmt").hex(), fixed_5204a=L.dump(0x5204A + DELTA, 4, "fx").hex())
        elif nat == BP_SWEEP:
            ent.update(name="call unit_death_sweep", ebx_reward_rows=r["EBX"], g=globs())
        elif nat == BP_SWEEP_RET:
            ent.update(name="unit_death_sweep 返回", units=unit_rows())
        elif nat == BP_GRANT:
            st = stack(r, 3)
            ent.update(name="call grant_reward_rows", args=[st[0], st[1], hex(st[2])], rows=L.dump(st[2], 12, "rw").hex())
        elif nat == BP_DISP_END:
            ent.update(name="item_effect_dispatch 收尾", g=globs(), units=unit_rows())
        elif nat == BP_POST:
            ent.update(name="item_effect_dispatch 返回(ai_item_action 內)", g=globs())
            frame(tag, "post", 0)
            L.shot(f"{tag}_post")
        elif nat == BP_RET:
            ent.update(name="ai_item_action 返回前", g=globs())
        elif nat in LOSE:
            st = stack(r, 2)
            ent.update(name="戰敗畫面 0x22e5c" if nat == BP_LOSE else "title_menu_dispatch 入口", ret=hex(st[0] - DELTA), g=globs())
        else:
            ent.update(name="不是設的斷點", regs={k: hex(v) for k, v in r.items()})
            log["stops"].append(ent)
            print(ent)
            break
        log["stops"].append(ent)
        print({k: v for k, v in ent.items() if k not in ("units", "resist_tbl") and not k.startswith("tbl_")})
        if nat == BP_RET:
            reset_bps(LOSE)
            done = True
            time.sleep(0.5)
            L.cmd("BPLIST")
            time.sleep(0.5)
            print("\n".join(L.pane().splitlines()[-6:]))
            L.resume()
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("stops", len(log["stops"]), "done", done)
    return 0 if done else 1


def watch(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "stops": []}
    t0 = time.time()
    while time.time() - t0 < max_s:
        r = L.wait_stop(max_s - (time.time() - t0), poll=0.7)
        if r is None:
            print("沒有停(逾時)")
            break
        nat = r.get("EIP", 0) - DELTA
        st = stack(r, 2)
        ent = {"at": hex(nat), "t": round(time.time() - t0, 1), "ret": hex(st[0] - DELTA), "g": globs()}
        if nat == BP_LOSE:
            ent["units"] = [u for u in unit_rows() if u["i"] in (0, 3, 11)]
        log["stops"].append(ent)
        print(ent)
        if nat == BP_TITLE or nat not in LOSE:
            reset_bps(())
            L.resume()
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return 0 if any(s["at"] == hex(BP_TITLE) for s in log["stops"]) else 1


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "bpdel":
        reset_bps(())
        time.sleep(0.5)
        L.cmd("BPLIST")
        time.sleep(0.5)
        print("\n".join(L.pane().splitlines()[-6:]))
    elif cmd in ("rec", "watch"):
        L.ubase = L.ubase or int((OUT / "ubase.txt").read_text())
        if cmd == "watch":
            return watch(argv[1], float(argv[2]) if len(argv) > 2 else 300)
        return rec(argv[1], float(argv[2]) if len(argv) > 2 else 500, int(argv[3]) if len(argv) > 3 else None)
    elif cmd in ("units", "arm"):
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        (OUT / "ubase.txt").write_text(str(L.ubase))
        try:
            if cmd == "arm":
                s_hp, x, y = int(argv[1]), int(argv[2]), int(argv[3])
                L.sm(L.ua(11, 0xE), bytes([0x00, 79]))
                L.sm(L.ua(11, 0), bytes([x, y]))
                if s_hp >= 0:
                    L.sm(L.ua(0, 0x40), struct.pack("<h", s_hp))
                L.sm(L.ua(0, 5), bytes([0]))
                for i in (1, 2, 3, 4):
                    L.sm(L.ua(i, 5), bytes([0x80]))
                u0 = L.dump(L.ua(0, 0), 2, "u0xy")
                L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
                print("row3 before", L.dump(SPELL_ROW3_HIT - 2 + DELTA, 7, "row3").hex())
                if len(argv) > 4:
                    L.sm(SPELL_ROW3_HIT + DELTA, bytes([int(argv[4])]))
                    print("row3 after ", L.dump(SPELL_ROW3_HIT - 2 + DELTA, 7, "row3").hex())
                reset_bps(REST + (BP_ENTRY,) + LOSE)
                time.sleep(0.5)
            show()
            if cmd == "arm":
                L.cmd("BPLIST")
                time.sleep(0.5)
                print("\n".join(L.pane().splitlines()[-12:]))
        finally:
            L.resume()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
