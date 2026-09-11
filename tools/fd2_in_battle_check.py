#!/usr/bin/env python3
"""判定「真的在戰鬥中」——用單位陣列的內部一致性,不用單一全域。

為什麼需要:第一版偵測器只看 `[0x53bef]==1`(回合)與 `[0x53beb]!=0`(單位數),
在標題畫面就成立了(讀到 turn=1 / units=21),因為戰鬥還不存在時那兩個全域是殘值。
單位陣列當場自證那是垃圾:HP 3911、MP 1026、AP 4178、HIT 2664。

真正有鑑別力的是**內部一致性**:真單位的欄位彼此有界且互相吻合。
不合理的組合(HP 上千、AP 上千)在遊戲規則下不可能出現,而殘值幾乎必然違反。

判準的擁有權(2026-09-09)
--------------------------
同一條「單位記錄是否可信」的判準有兩個使用端:本檔的 `why()` 與
`fd2_game_state.classify_units()`。它們**曾經各走各的**:2026-09-04 發現
`maxHP <= 9999` 這個界線與本專案自己的 `fd2_stat_override` 工作流衝突
(把 HP 覆寫成 9999 之後單位一升級就變 10016),`fd2_game_state` 把界線放寬到
u16 上限並寫下理由,而本檔**沒有跟著改**——偏偏 `fd2_game_state` 的 docstring
還寫著 NOT_IN_BATTLE 的判準「見 fd2_in_battle_check.py」,也就是它引用的正是
沒修的那一支。這正是本檔開頭在講的「每支工具各自實作半套判斷」再次發生。

界線現已統一(`MAX_HP_CEILING`),並由兩邊的 selftest 互相對照:同一組單位記錄
必須得到一致的判斷。本檔的純邏輯(`parse_rows` / `why` / `verdict`)不再寫在
模組層,否則 import 就會觸發實機呼叫,誰也沒辦法對它寫測試——那才是它會漂移
的真正原因。

用法:
    python fd2_in_battle_check.py <instance>   → 印 IN_BATTLE / NOT_IN_BATTLE,exit 0/1
    python fd2_in_battle_check.py --selftest
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 單位記錄可信度的共用界線。刻意放在模組層並由 fd2_game_state 的 selftest
# 反向對照,讓「兩支各自寫一個數字」這件事在下次發生時就被擋下。
MAX_HP_CEILING = 0xFFFF     # 見上方「判準的擁有權」;原為 9999,與 stat_override 衝突
VALID_CAMPS = (0x00, 0x01, 0x02)
MIN_OUR_UNITS = 2           # 我方(camp 0x02)存活單位少於這個數就不算在戰鬥


def why(r):
    """單一單位記錄不可信的理由;可信回 None。

    maxHP==0 是**未使用的空槽**,不是損毀:`[0x53beb]` 的計數會涵蓋空槽
    (ch27 實測 63 槽裡就有數個)。把空槽算成錯誤會再次誤判整場戰鬥。

    2026-09-04 修正:第一版把 AP/DP/HIT 當 byte(<=255)、HP/MP 上限 999。
    那是**假設,不是不變量**,而且是錯的:在 ch27 的測試存檔上,單位真的有
    AP 938 / MP 817 / HP 782,於是這支檢查把一場**真的正在進行的戰鬥**judge 成
    NOT_IN_BATTLE。它錯得很有說服力(數字看起來就是垃圾),直到畫面上的狀態卡
    顯示「悠妮 LV-02 HP 782 MP 817」與記憶體逐欄吻合,才證明讀取一直是對的。
    現在只用**結構性**不變量,不對遊戲數值大小做假設。
    """
    if r["mhp"] == 0 and r["hp"] == 0 and r["mp"] == 0:
        return None
    if not 0 < r["mhp"] <= MAX_HP_CEILING:
        return f"maxHP={r['mhp']}"
    if r["hp"] > r["mhp"]:
        return f"HP{r['hp']}>maxHP{r['mhp']}"
    if r["camp"] not in VALID_CAMPS:
        return f"camp={r['camp']:#04x}"
    return None


def parse_rows(text):
    """把 helper 的 read-unit-array 輸出解成記錄清單。"""
    rows = []
    for ln in text.splitlines():
        m = re.match(r"\s*(\d+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+"
                     r"(\d+)/(\d+)\s+(\d+)/(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", ln)
        if m:
            g = m.groups()
            rows.append({"idx": int(g[0]), "camp": int(g[1], 16), "hp": int(g[4]),
                         "mhp": int(g[5]), "mp": int(g[6]), "ap": int(g[8]),
                         "dp": int(g[9]), "hit": int(g[10])})
    return rows


def verdict(rows):
    """(exit code, 訊息)。0 = IN_BATTLE,1 = NOT_IN_BATTLE。"""
    if not rows:
        return 1, "NOT_IN_BATTLE: 讀不到單位陣列"
    bad = [(r, why(r)) for r in rows if why(r)]
    if bad:
        return 1, (f"NOT_IN_BATTLE: {len(bad)}/{len(rows)} 筆(計數內)欄位超界,"
                   f"例:idx{bad[0][0]['idx']} {bad[0][1]}")
    ours = [r for r in rows if r["camp"] == 0x02 and r["hp"] > 0]
    if len(ours) < MIN_OUR_UNITS:
        return 1, f"NOT_IN_BATTLE: 我方(camp 0x02)存活單位只有 {len(ours)} 個"
    return 0, (f"IN_BATTLE: 計數內 {len(rows)} 筆全部通過界線檢查,我方 {len(ours)} 人;"
               f"樣本 idx{ours[0]['idx']} HP{ours[0]['hp']}/{ours[0]['mhp']} "
               f"AP{ours[0]['ap']}")


def _rec(idx=0, camp=0x02, hp=100, mhp=100, mp=0, ap=10, dp=10, hit=50):
    return {"idx": idx, "camp": camp, "hp": hp, "mhp": mhp, "mp": mp,
            "ap": ap, "dp": dp, "hit": hit}


def selftest() -> int:
    """純邏輯的對照。實機取得那一層不在範圍內,這是刻意的範圍限制。"""
    import fd2_game_state as GS
    fails = []

    print("(1) 判準漂移回歸:maxHP 界線必須與 fd2_game_state 一致")
    # 2026-09-04 的 stat_override 衝突(HP 覆寫 9999 後升級變 10016)在
    # fd2_game_state 修了、本檔沒修,而前者的 docstring 還把後者當權威。
    live = [_rec(0, 0x02, 782, 10016), _rec(1, 0x02, 50, 60), _rec(2, 0x00, 30, 40)]
    rc, msg = verdict(live)
    gs_state, gs_msg = GS.classify_units(
        [{"index": r["idx"], "camp": r["camp"], "hp_cur": r["hp"], "hp_max": r["mhp"]}
         for r in live])
    ok1 = (rc == 0 and gs_state != GS.GameState.NOT_IN_BATTLE
           and MAX_HP_CEILING == 0xFFFF)
    print(f"    {'PASS' if ok1 else 'FAIL'}: 升級後 maxHP=10016 -> 本檔 rc={rc}"
          f"(應 0)、fd2_game_state={gs_state.value}(不得 NOT_IN_BATTLE)")
    if not ok1:
        fails.append(f"界線仍不一致:rc={rc}、gs={gs_state}")

    print("\n(2) 舊界線必須真的會判錯(證明第 (1) 題不是恆真)")
    old_bad = [r for r in live if not (0 < r["mhp"] <= 9999)]
    ok2 = len(old_bad) == 1 and old_bad[0]["mhp"] == 10016
    print(f"    {'PASS' if ok2 else 'FAIL'}: 用舊的 <=9999 會有 {len(old_bad)} 筆被判超界"
          f"(應 1,即 maxHP=10016 那筆)")
    if not ok2:
        fails.append(f"舊界線對照不成立:{old_bad}")

    print("\n(3) 兩支工具對同一組記錄必須給出一致方向的判斷")
    cases = {
        "正常戰鬥": [_rec(0, 0x02, 50, 60), _rec(1, 0x02, 40, 40), _rec(2, 0x00, 30, 40)],
        "空槽混雜": [_rec(0, 0x02, 50, 60), _rec(1, 0x02, 40, 40),
                     _rec(2, 0x00, 30, 40), _rec(3, 0x00, 0, 0)],
        "HP>maxHP": [_rec(0, 0x02, 99, 60), _rec(1, 0x02, 40, 40), _rec(2, 0x00, 30, 40)],
        "camp 超界": [_rec(0, 0x07, 50, 60), _rec(1, 0x02, 40, 40), _rec(2, 0x00, 30, 40)],
        "全空槽": [_rec(0, 0x02, 0, 0), _rec(1, 0x02, 0, 0)],
    }
    disagree = []
    for name, rows in cases.items():
        rc, _ = verdict(rows)
        st, _ = GS.classify_units(
            [{"index": r["idx"], "camp": r["camp"], "hp_cur": r["hp"], "hp_max": r["mhp"]}
             for r in rows])
        mine_ok = rc == 0
        gs_ok = st not in (GS.GameState.NOT_IN_BATTLE,)
        if mine_ok != gs_ok:
            disagree.append((name, rc, st.value))
    ok3 = not disagree
    print(f"    {'PASS' if ok3 else 'FAIL'}: {len(cases)} 個案例"
          + ("方向全部一致" if ok3 else f",不一致 {disagree}"))
    if not ok3:
        fails.append(f"兩支工具判斷方向不一致:{disagree}")

    print("\n(3b) parse_rows 的欄位對應 + maxHP/HP 的下界")
    # 2026-09-11 窮舉突變測試:parse_rows 從來沒被任何一行 helper 輸出測過,群組索引
    # g[5]/g[6]/g[8]/g[9]/g[10] 改成相鄰欄位全部逃掉。這行每一欄都放不同的數字,
    # 取錯欄一定看得出來。另兩個下界:maxHP=1 是合法值、HP=1 的我方單位算存活。
    line = "  3 0x02 0x10 0x20 11/22 33/44 55 66 77 88"
    got = parse_rows(line)
    want = [{"idx": 3, "camp": 2, "hp": 11, "mhp": 22, "mp": 33, "ap": 55, "dp": 66, "hit": 77}]
    alive = [_rec(i, 0x02, 1, 1) for i in range(max(MIN_OUR_UNITS, 1))] + [_rec(9, 0x00, 5, 5)]
    b3 = {"欄位對應": got == want,
          "maxHP=1 合法": why(_rec(0, 0x02, 1, 1)) is None,
          "HP=1 算存活": verdict(alive)[0] == 0}
    ok3b = all(b3.values())
    print(f"    {'PASS' if ok3b else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b3.items())
          + ("" if b3["欄位對應"] else f";實得 {got}"))
    if not ok3b:
        fails.append(f"parse_rows/下界不對:{[k for k, v in b3.items() if not v]}")

    print("\n(4) 非平凡性 + 負向控制")
    rcs = {verdict(rows)[0] for rows in cases.values()}
    empty_rc, empty_msg = verdict([])
    ok4 = rcs == {0, 1} and empty_rc == 1 and "讀不到" in empty_msg
    print(f"    {'PASS' if ok4 else 'FAIL'}: 5 個案例給出 {sorted(rcs)} 兩種判斷、"
          f"空陣列 -> rc={empty_rc}")
    if not ok4:
        fails.append(f"判斷恆定或空輸入處理不正確:{sorted(rcs)} / {empty_rc}")

    print("\n(5) parse_rows:helper 輸出格式解析")
    sample = ("  0  0x02 0x00 0x01  782/10016  817/900  938  120  85  7\n"
              "  1  0x00 0x00 0x00  30/40  0/0  12  8  50  3\n"
              "垃圾行,不該被解進來\n")
    parsed = parse_rows(sample)
    ok5 = (len(parsed) == 2 and parsed[0]["mhp"] == 10016 and parsed[0]["camp"] == 0x02
           and parsed[1]["camp"] == 0x00 and parsed[0]["hp"] == 782)
    print(f"    {'PASS' if ok5 else 'FAIL'}: 解出 {len(parsed)} 筆(應 2,垃圾行不計)、"
          f"首筆 HP{parsed[0]['hp'] if parsed else '?'}/"
          f"{parsed[0]['mhp'] if parsed else '?'}")
    if not ok5:
        fails.append(f"parse_rows 不正確:{parsed}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(判準漂移回歸 + 舊界線對照 + 跨工具一致性 "
          "+ 非平凡性與負向控制 + 解析)。實機取得層未涵蓋,見 docstring。")
    return 0


def main(argv):
    """實機取得層。**整段必須留在函式裡**——2026-09-09:這些原本寫在模組層,
    於是任何 import 它的行程都會觸發實機呼叫;更直接的後果是
    `fd2_game_state --selftest` 一 import 本檔,本檔看到 argv 裡的 `--selftest`
    就自己跑起來並 `sys.exit`,把另一支工具的 selftest 整個蓋掉。
    純邏輯要能被 import 測試,就不能有模組層副作用。
    """
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        # 2026-09-04:少了這道 guard 時,無參數呼叫會直接 IndexError 崩潰,
        # 而 verify_all_tools 的 invoke 層就是這樣抓到它的。
        print(__doc__)
        print("用法: fd2_in_battle_check.py <instance>")
        return 2
    if argv[1] == "--selftest":
        return selftest()

    inst = argv[1]
    helper = [sys.executable, "tools/fd2_dosbox_live_helper.py"]

    def run(*a):
        return subprocess.run(helper + list(a), capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout

    # 2026-09-04:先確認遊戲還在,再解讀任何記憶體值。
    # FD2.EXE 退回 DOS 之後,這些位址仍留著舊值,而單位陣列**不一定讀失敗**——
    # 實測到過「讀取成功、12 筆、內容是垃圾」。本檔的陣營值域與 HP 界線檢查那次
    # 擋住了,但那是殘留內容剛好夠亂;落在合法範圍的殘留值會讓它對著一個已死的
    # 遊戲回報 IN_BATTLE。「讀得到」從來就不等於「遊戲活著」,這道閘門才是。
    import fd2_dosbox_live_helper as _H
    alive, meas = _H.game_alive(inst)
    if not alive:
        print(f"GAME_NOT_RUNNING: 畫面判定 FD2.EXE 已不在執行"
              f"(相異顏色 {meas['distinct_colors']}、非黑 {meas['nonblack_ratio']});"
              f"此時的記憶體讀值是殘留,**不可解讀為戰鬥狀態**")
        return 3

    run("enter-debugger", "--instance", inst)
    # 只驗「單位數 [0x53beb]」之內的記錄。第一版固定驗 16 筆,把計數之外的殘值
    # 也算進去,於是在真正進到戰鬥(12 單位)之後仍然回報 NOT_IN_BATTLE——
    # 檢查超出有效範圍,和誤把殘值當資料是同一類錯誤。
    cnt_out = run("mem", "read-global", "--instance", inst, "--selector", "0170",
                  "--ghidra-addr", "53beb", "--bytecount", "4")
    m = re.search(r"u8=(\d+)", cnt_out)
    count = int(m.group(1)) if m else 0
    if not (2 <= count <= 96):
        run("resume", "--instance", inst)
        print(f"NOT_IN_BATTLE: 單位數 [0x53beb]={count} 不在合理範圍")
        return 1
    out = run("mem", "read-unit-array", "--instance", inst, "--selector", "0170",
              "--num-records", str(count))
    run("resume", "--instance", inst)

    # 2026-09-09:這裡原本有**第二份 `why()`**,定義在模組層、覆蓋掉上面那個,
    # 而且帶著舊的 `maxHP <= 9999`。判準漂移就是這樣發生的:兩份同名邏輯,改了
    # 一份不會有任何東西報錯。現在只留一份(見檔頭的 `why`)。
    rc, msg = verdict(parse_rows(out)[:count])
    print(msg)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
