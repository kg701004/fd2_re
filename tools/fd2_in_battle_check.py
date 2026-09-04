#!/usr/bin/env python3
"""判定「真的在戰鬥中」——用單位陣列的內部一致性,不用單一全域。

為什麼需要:第一版偵測器只看 `[0x53bef]==1`(回合)與 `[0x53beb]!=0`(單位數),
在標題畫面就成立了(讀到 turn=1 / units=21),因為戰鬥還不存在時那兩個全域是殘值。
單位陣列當場自證那是垃圾:HP 3911、MP 1026、AP 4178、HIT 2664。

真正有鑑別力的是**內部一致性**:真單位的欄位彼此有界且互相吻合。
不合理的組合(HP 上千、AP 上千)在遊戲規則下不可能出現,而殘值幾乎必然違反。
用法:in_battle.py <instance>  → 印 IN_BATTLE / NOT_IN_BATTLE 與理由,exit 0/1
"""
import re
import subprocess
import sys

if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
    # 2026-09-04:少了這道 guard 時,無參數呼叫會直接 IndexError 崩潰,
    # 而 verify_all_tools 的 invoke 層就是這樣抓到它的。
    print(__doc__)
    print("用法: fd2_in_battle_check.py <instance>")
    sys.exit(2)

INST = sys.argv[1]
H = [sys.executable, "tools/fd2_dosbox_live_helper.py"]

# 2026-09-04:先確認遊戲還在,再解讀任何記憶體值。
# FD2.EXE 退回 DOS 之後,這些位址仍留著舊值,而單位陣列**不一定讀失敗**——
# 實測到過「讀取成功、12 筆、內容是垃圾」。本檔的陣營值域與 HP 界線檢查那次擋住了,
# 但那是殘留內容剛好夠亂;落在合法範圍的殘留值會讓它對著一個已死的遊戲回報 IN_BATTLE。
# 「讀得到」從來就不等於「遊戲活著」,這道閘門才是。
import os  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fd2_dosbox_live_helper as _H  # noqa: E402

_alive, _meas = _H.game_alive(INST)
if not _alive:
    print(f"GAME_NOT_RUNNING: 畫面判定 FD2.EXE 已不在執行"
          f"(相異顏色 {_meas['distinct_colors']}、非黑 {_meas['nonblack_ratio']});"
          f"此時的記憶體讀值是殘留,**不可解讀為戰鬥狀態**")
    sys.exit(3)


def run(*a):
    return subprocess.run(H + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


run("enter-debugger", "--instance", INST)
# 只驗「單位數 [0x53beb]」之內的記錄。第一版固定驗 16 筆,把計數之外的殘值
# 也算進去,於是在真正進到戰鬥(12 單位)之後仍然回報 NOT_IN_BATTLE——
# 檢查超出有效範圍,和誤把殘值當資料是同一類錯誤。
cnt_out = run("mem", "read-global", "--instance", INST, "--selector", "0170",
              "--ghidra-addr", "53beb", "--bytecount", "4")
m = re.search(r"u8=(\d+)", cnt_out)
count = int(m.group(1)) if m else 0
if not (2 <= count <= 96):
    run("resume", "--instance", INST)
    print(f"NOT_IN_BATTLE: 單位數 [0x53beb]={count} 不在合理範圍")
    sys.exit(1)
out = run("mem", "read-unit-array", "--instance", INST, "--selector", "0170",
          "--num-records", str(count))
run("resume", "--instance", INST)

rows = []
for ln in out.splitlines():
    m = re.match(r"\s*(\d+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+"
                 r"(\d+)/(\d+)\s+(\d+)/(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", ln)
    if m:
        g = m.groups()
        rows.append({"idx": int(g[0]), "camp": int(g[1], 16), "hp": int(g[4]),
                     "mhp": int(g[5]), "mp": int(g[6]), "ap": int(g[8]),
                     "dp": int(g[9]), "hit": int(g[10])})

if not rows:
    print("NOT_IN_BATTLE: 讀不到單位陣列"); sys.exit(1)

# 2026-09-04 修正:第一版把 AP/DP/HIT 當 byte(<=255)、HP/MP 上限 999。
# 那是**假設,不是不變量**,而且是錯的:在 ch27 的測試存檔上,單位真的有
# AP 938 / MP 817 / HP 782,於是這支檢查把一場**真的正在進行的戰鬥**judge 成
# NOT_IN_BATTLE。它錯得很有說服力(數字看起來就是垃圾),直到畫面上的狀態卡
# 顯示「悠妮 LV-02 HP 782 MP 817」與記憶體逐欄吻合,才證明讀取一直是對的。
#
# 改成只用**結構性**不變量,不再對遊戲數值大小做假設:
#   * maxHP 必須為正(殘值常是 0 或極大)
#   * HP <= maxHP(欄位錯位時幾乎必然違反)
#   * camp 必須是小列舉值(0/1/2)
# maxHP 仍保留一個很鬆的上限,只為了擋掉像 42421 這種明顯的殘值。
def why(r):
    # maxHP==0 是**未使用的空槽**,不是損毀:`[0x53beb]` 的計數會涵蓋空槽
    # (ch27 實測 63 槽裡就有數個)。把空槽算成錯誤會再次誤判整場戰鬥。
    if r["mhp"] == 0 and r["hp"] == 0 and r["mp"] == 0:
        return None
    if not 0 < r["mhp"] <= 9999: return f"maxHP={r['mhp']}"
    if r["hp"] > r["mhp"]:       return f"HP{r['hp']}>maxHP{r['mhp']}"
    if r["camp"] not in (0x00, 0x01, 0x02): return f"camp={r['camp']:#04x}"
    return None

rows = rows[:count]
bad = [(r, why(r)) for r in rows if why(r)]
ours = [r for r in rows if r["camp"] == 0x02 and r["hp"] > 0]
if bad:
    print(f"NOT_IN_BATTLE: {len(bad)}/{len(rows)} 筆(計數內)欄位超界,"
          f"例:idx{bad[0][0]['idx']} {bad[0][1]}")
    sys.exit(1)
if len(ours) < 2:
    print(f"NOT_IN_BATTLE: 我方(camp 0x02)存活單位只有 {len(ours)} 個")
    sys.exit(1)
print(f"IN_BATTLE: 計數內 {len(rows)} 筆全部通過界線檢查,我方 {len(ours)} 人;"
      f"樣本 idx{ours[0]['idx']} HP{ours[0]['hp']}/{ours[0]['mhp']} AP{ours[0]['ap']}")
sys.exit(0)
