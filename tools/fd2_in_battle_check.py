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

INST = sys.argv[1]
H = [sys.executable, "tools/fd2_dosbox_live_helper.py"]


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

# 界線取得寬鬆,只求排除殘值;真實 ch01 值(HP 28-50、AP 11-26、HIT 86-97)離界很遠。
def why(r):
    if not 0 < r["mhp"] <= 999: return f"maxHP={r['mhp']}"
    if r["hp"] > r["mhp"]:      return f"HP{r['hp']}>maxHP{r['mhp']}"
    if r["mp"] > 999:           return f"MP={r['mp']}"
    if r["ap"] > 255:           return f"AP={r['ap']}"
    if r["dp"] > 255:           return f"DP={r['dp']}"
    if r["hit"] > 255:          return f"HIT={r['hit']}"
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
