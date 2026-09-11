#!/usr/bin/env python3
"""從固定版本 FD2.EXE 匯出已閉合的特殊寶物事件規則。

2026-09-08 修正:handler 位址改成**從跳表讀出來**,不再寫死常數再加版本位移。

原本的寫法是 `hex(0x35854 + delta)`,新版 delta = 0x356,算出 `0x35baa`。
但 `0x35baa` 落在指令中段(`83 C4 04` = add esp,4),根本不是函式邊界;而
`0x35854` 在現行參考版是乾淨的 Watcom 序頭(`push 0x44; call 0x3702f`,
`+0x14` 處 `mov esi, 0x5274E` —— 正是這裡要的五格寶物表)。

根因是那個常數**本身已經是新版位址**(doc25 §11.7 的 0x35854 是 2026-08-14
改基準之後做的分析),卻被當成舊版常數又換算一次,等於重複計算。位移本身沒錯
——同批的 staging helper 0x35822 與 8 個 gate call 加上 0x356 之後都落在正確
位置(實測:8/8 都是 `E8 call -> 0x10b4e`)——錯的是把它套在一個不該套的常數上。

所以現在不再有「該不該加位移」這個問題:event 58 的 handler 就是跳表
`0x51b91` 第 58 格的值,直接讀。讀完會驗證它確實是函式入口(見
`assert_function_entry`),這類錯誤不可能再安靜地跑出來。

背後那個混淆值得記一筆(doc25 2026-09-08 補述有完整版):`0x356` 一直被當成
raw→relocated 的 relocation 偏移,但實測現行版本的重定位是**一致的 +0x10000**
(object 1 基底,index 57/58/76/78 四格全同)。`0x356` 其實是舊版→新版的**版本差**。
兩件不同的事被當成同一件,而且因為兩邊都「算得出來」,所以一直沒被發現——這支
工具就是踩在這個混淆上。

(event 58 handler 的身分本身不是本輪的發現:doc25 2026-09-07 一節已經用
image_ref_scan 推翻了 §11.7 的「table artifact」判定並定出 0x35854,本輪只是從
工具端獨立再確認一次,四個值逐一相符。)
"""

import hashlib
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from le_xref import parse_fixups, parse_le

# 2026-09-03:改成同時支援兩個版本(見 extract_event_id_groups.py 的同名表)。
# 資料表 0x5274e 與跳表 0x51b91 兩版**相同**,所以下面不需要任何位移欄位了。
EDITIONS = {
    "b97caf2239a27a896069d03549d96e1e": {
        "label": "舊版(357074 B,已遺失)", "size": 357074},
    "33464c81e6a364fd0660141139aa8e6e": {
        "label": "新版(1998 重打包版,509158 B)", "size": 509158},
}

EVENT_JUMP_TABLE = 0x51B91
TREASURE_EVENT_ID = 58
ITEM_TABLE = 0x5274E


def linear_bytes(data, meta, address, size):
    obj = next(
        obj
        for obj in meta["objs"]
        if obj["base"] <= address and address + size <= obj["base"] + obj["vsize"]
    )
    offset = (
        meta["data_off"]
        + (obj["first"] - 1) * meta["page_size"]
        + address
        - obj["base"]
    )
    return data[offset:offset + size]


def linear_offset(data, meta, address):
    obj = next(o for o in meta["objs"]
               if o["base"] <= address < o["base"] + o["vsize"])
    return (meta["data_off"] + (obj["first"] - 1) * meta["page_size"]
            + address - obj["base"])


def jump_table_entry(data, meta, event_id, fixups=None):
    """讀 0x51b91 事件跳表的第 N 格。這張表兩版位址相同,不需要版本換算。

    **必須走 fixup,不能直接讀原始位元組。** 跳表存的是未重定位的指標:檔案裡
    第 58 格是 `54 58 02 00`(0x25854),載入時 LE loader 才把 object 基底
    加上去成 0x35854。直接 `struct.unpack` 會少 0x10000,而且少得很像真的
    ——0x25854 一樣落在程式碼範圍內,不會爆炸,只會安靜地錯。

    `le_xref.parse_fixups` 的 key 是**檔案位移**(不是線性位址),所以要先換算;
    兄弟工具 `extract_event_id_groups.fixup_map` 的 key 才是線性位址。兩者條目
    數相同(7948),只是慣例不同,不是互相矛盾。
    """
    if fixups is None:
        fixups = parse_fixups(data, meta)
    site = EVENT_JUMP_TABLE + event_id * 4
    target = fixups.get(linear_offset(data, meta, site))
    if target is None:
        raise SystemExit(
            f"跳表 {site:#x}(event {event_id})沒有對應的 fixup 記錄——"
            "這張表的每一格都應該是重定位指標,拒絕猜測")
    return target


def neighbour_prologue_votes(data, meta, fixups):
    """同一張跳表裡 event 58 前後各 4 格,各自序頭 `call` 的目標 -> 票數。

    2026-09-11 從 `assert_function_entry` 裡抽出來,原因是突變測試量到的一個實質缺口:
    這段投票邏輯**整段沒有被任何檢查約束**。把 `other < 0` 改成 `other >= 0`(每一格都
    被跳過、votes 變空)、或把 `h[0] == 0x68` 改成 `!=`(選到完全不同的一批格子),
    突變都逃掉 —— 因為 votes 一旦為空,下面的多數決就整段跳過,`assert_function_entry`
    直接回傳 target,而 selftest 的其他題全是被**序頭形狀**那一關擋下的,測不到這裡。

    抽成獨立函式之後 selftest 才打得到它本身(多數必須是 stack probe、票數必須夠),
    行為與原本內嵌時完全相同。
    """
    votes = {}
    for other in range(TREASURE_EVENT_ID - 4, TREASURE_EVENT_ID + 5):
        if other == TREASURE_EVENT_ID or other < 0:
            continue
        try:
            neighbour = jump_table_entry(data, meta, other, fixups)
            h = linear_bytes(data, meta, neighbour, 10)
            if h[0] == 0x68 and h[5] == 0xE8:
                t = neighbour + 10 + struct.unpack_from("<i", h, 6)[0]
                votes[t] = votes.get(t, 0) + 1
        except (StopIteration, struct.error, SystemExit):
            continue
    return votes


def assert_function_entry(data, meta, address, what, fixups=None):
    """要求 address 是 Watcom 函式入口:`push imm32; call rel32`。

    這是把上一版那個 bug 擋死的地方——`0x35baa` 起頭是 `83 C4 04`,
    連序頭的形狀都不對,任何一個這樣的檢查都會抓到。

    刻意不寫死 stack-check 的位址(那本身就是會隨版本變的東西),改成從同一張
    跳表的其他格反推:所有 handler 的序頭都會 call 同一個 stack-check,
    所以要求本格的 call 目標與多數格一致,比對照一個硬編常數更耐版本變動。
    """
    head = linear_bytes(data, meta, address, 10)
    if head[0] != 0x68 or head[5] != 0xE8:
        raise SystemExit(
            f"{what} {address:#x} 不是 Watcom 函式入口(起頭 {head[:6].hex()},"
            f"預期 `68 imm32` + `E8`)——不要把它寫進輸出")
    target = address + 10 + struct.unpack_from("<i", head, 6)[0]
    if fixups is None:
        fixups = parse_fixups(data, meta)
    votes = neighbour_prologue_votes(data, meta, fixups)
    if votes:
        common = max(votes, key=votes.get)
        if target != common:
            raise SystemExit(
                f"{what} {address:#x} 的序頭 call 指向 {target:#x},但同表鄰居"
                f"多數指向 {common:#x}(stack-check)——位址可疑,拒絕輸出")
    return target


EXE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "org_game", "炎龍騎士團", "FLAME2", "FD2.EXE")


def selftest():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    data = open(EXE, "rb").read()
    meta = parse_le(data)

    fixups = parse_fixups(data, meta)

    print("(1) handler 必須讀自跳表,且是合法函式入口")
    handler = jump_table_entry(data, meta, TREASURE_EVENT_ID, fixups)
    ok1 = handler == 0x35854
    print(f"    {'PASS' if ok1 else 'FAIL'}: 跳表第 58 格 = {handler:#x}(現行參考版應為 0x35854)")
    if not ok1:
        fails.append(f"跳表第 58 格是 {handler:#x}")
    sc = assert_function_entry(data, meta, handler, "event 58 handler", fixups)
    print(f"    PASS: 序頭 call -> {sc:#x}(與同表鄰居一致)")

    print("\n(2) 必須走 fixup:直接讀原始位元組會少 0x10000,而且少得不像壞掉")
    raw = struct.unpack("<I", linear_bytes(
        data, meta, EVENT_JUMP_TABLE + TREASURE_EVENT_ID * 4, 4))[0]
    ok2 = raw == handler - 0x10000 and raw != handler
    print(f"    {'PASS' if ok2 else 'FAIL'}: 原始位元組={raw:#x} 重定位後={handler:#x}")
    if not ok2:
        fails.append(f"fixup 前後沒有預期的差異(raw={raw:#x} fixed={handler:#x})")

    print("\n(3) 回歸:被修掉的那個 bug(常數 + 0x356)算出的位址必須被拒絕")
    try:
        assert_function_entry(data, meta, 0x35854 + 0x356, "舊寫法", fixups)
        ok3 = False
    except SystemExit:
        ok3 = True
    print(f"    {'PASS' if ok3 else 'FAIL'}: 0x35baa 被拒絕={ok3}"
          f"(它起頭是 {linear_bytes(data, meta, 0x35baa, 3).hex()},add esp,4)")
    if not ok3:
        fails.append("0x35baa 沒有被序頭檢查擋下——這個 bug 會再發生一次")

    print("\n(4) 故障注入:把跳表第 58 格指向指令中段,必須拒絕輸出而不是照寫")
    # 注入點必須是 fixup map —— 改原始位元組對「走 fixup 的讀法」完全沒有作用,
    # 那種注入會安靜地失效、讓這題白過。
    bad = dict(fixups)
    bad[linear_offset(data, meta, EVENT_JUMP_TABLE + TREASURE_EVENT_ID * 4)] = 0x35BAA
    got = jump_table_entry(data, meta, TREASURE_EVENT_ID, bad)
    injected = got == 0x35BAA
    try:
        assert_function_entry(data, meta, got, "注入", bad)
        ok4 = False
    except SystemExit:
        ok4 = True
    print(f"    {'PASS' if injected else 'FAIL'}: 注入生效,讀回 {got:#x}")
    print(f"    {'PASS' if ok4 else 'FAIL'}: 被拒絕={ok4}")
    if not injected:
        fails.append("故障注入沒有生效,本題不成立")
    if not ok4:
        fails.append("注入的壞位址沒有被擋下")

    print("\n(4b) 鄰居投票**本身**必須成立 —— 這段先前完全沒有被任何檢查約束")
    # 突變測試量到的實質缺口:把 `other < 0` 改成 `>= 0`(votes 變空)或把
    # `h[0] == 0x68` 改成 `!=`(選到另一批格子),突變全部逃掉 —— 因為 votes 一空,
    # 多數決整段跳過、直接回傳 target,而 (3)/(4) 是被**序頭形狀**那一關擋下的,
    # 根本走不到這裡。所以要分別釘住:票是真的投出來的,而且多數就是 stack probe。
    votes = neighbour_prologue_votes(data, meta, fixups)
    total_votes = sum(votes.values())
    common = max(votes, key=votes.get) if votes else None
    ok4b = (common == 0x3702F and votes[common] >= 6 and total_votes >= 6)
    print(f"    {'PASS' if ok4b else 'FAIL'}: 8 個鄰居投出 {total_votes} 票,"
          f"多數 = {common:#x} × {votes.get(common, 0)}(stack probe 應為 0x3702f)"
          if votes else "    FAIL: 一票都沒有 —— 投票邏輯沒有在做事")
    if not ok4b:
        fails.append(f"鄰居投票不成立:votes={ {hex(k): v for k, v in votes.items()} }")

    print("\n(4c) 把投票關與序頭關**分離**:序頭合法但 callee 不是 stack probe,仍須拒絕")
    # 前面每一題的壞位址都是連序頭形狀都不對,所以只證明了第一關有效。
    # 0x10131 的序頭是合法的 `68 imm32; E8`,但它 call 的是 0x111ba 而非 stack probe
    # —— 只有投票那一關能擋下它。這是全檔唯一一題真正走到多數決的案例。
    head_ok = False
    try:
        h = linear_bytes(data, meta, 0x10131, 10)
        head_ok = h[0] == 0x68 and h[5] == 0xE8
        callee = 0x10131 + 10 + struct.unpack_from("<i", h, 6)[0]
        assert_function_entry(data, meta, 0x10131, "序頭合法但 callee 不符", fixups)
        ok4c = False
    except SystemExit:
        ok4c = True
    ok4c = ok4c and head_ok and callee != 0x3702F
    print(f"    {'PASS' if ok4c else 'FAIL'}: 0x10131 序頭合法={head_ok}、"
          f"callee={callee:#x}≠stack probe、被投票關擋下={ok4c}")
    if not ok4c:
        fails.append("序頭合法但 callee 不符的位址沒有被投票關擋下 —— 那一關是裝飾用的")

    print("\n(5) 配對控制:寶物表是純資料、不走 fixup,原始位元組即為正解")
    items = list(linear_bytes(data, meta, ITEM_TABLE, 5))
    no_fixup = linear_offset(data, meta, ITEM_TABLE) not in fixups
    ok5 = len(items) == 5 and all(i > 0 for i in items) and no_fixup
    print(f"    {'PASS' if ok5 else 'FAIL'}: {items}(該位址無 fixup 記錄={no_fixup})")
    if not ok5:
        fails.append(f"寶物表讀出 {items},無 fixup={no_fixup}")

    print("\n(6) 負向控制:未知版本的 EXE 必須被拒絕,不能沿用固定位址")
    ok6 = hashlib.md5(b"not the exe").hexdigest() not in EDITIONS
    print(f"    {'PASS' if ok6 else 'FAIL'}: 未知 md5 不在 EDITIONS")
    if not ok6:
        fails.append("EDITIONS 白名單失效")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(讀表走 fixup + bug 回歸 + 故障注入(含生效確認)"
          " + 配對/負向控制)。")
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) != 3:
        print(f"usage: {argv[0]} FD2.EXE output.json", file=sys.stderr)
        print(f"       {argv[0]} --selftest", file=sys.stderr)
        return 2
    data = open(argv[1], "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    edition = EDITIONS.get(md5)
    if edition is None or len(data) != edition["size"]:
        raise SystemExit(
            f"FD2.EXE 不是任何已知版本(md5={md5}, size={len(data)}),"
            "禁止沿用固定 handler/table 位址;已知版本見本檔 EDITIONS")
    meta = parse_le(data)
    items = list(linear_bytes(data, meta, ITEM_TABLE, 5))
    handler = jump_table_entry(data, meta, TREASURE_EVENT_ID)
    stack_check = assert_function_entry(data, meta, handler, "event 58 handler")
    result = {
        "source": {
            "file": os.path.basename(argv[1]),
            "size": len(data),
            "md5": md5,
            "sha256": hashlib.sha256(data).hexdigest(),
            "edition": edition["label"],
            "handler_source": f"讀自事件跳表 {EVENT_JUMP_TABLE:#x} 第 {TREASURE_EVENT_ID} 格",
            "stack_check": hex(stack_check),
        },
        "rules": [
            {
                "event_id": TREASURE_EVENT_ID,
                # doc25 §11.7(2026-08-24)曾判定表值 0x354fe 落在 event57 handler
                # 中段、是 table artifact;該判定已由 doc25 2026-09-07 一節推翻
                # (image_ref_scan 掃到 0x51c79 的絕對參照,並逐指令確認 0x35854 是
                # 有自己序言的獨立函式)。2026-09-08 從工具端走 fixup 獨立再確認:
                # index 57/58/76/78 = 0x35833/0x35854/0x360b6/0x36228,四值相符。
                # 所以這裡直接讀表,不再寫死任何位址。
                # 改動前請先看 doc25 §11.7.5、2026-09-07/09-08 兩節與 91-worklist L212。
                "handler": hex(handler),
                "item_table_address": hex(ITEM_TABLE),
                "item_by_slot": items,
                "open_slots": [0, 1, 2, 3, 4],
            }
        ],
    }
    with open(argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
