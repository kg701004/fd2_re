#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:把 20 名我方全設已行動(+5 = 0x80)、索爾與悠妮 DP 999,讓玩家回合自己結束;等到下一個玩家回合的 HUD 後讀事件狀態。
# 用法:skip_turn.sh <instance> <out_dir> <tag>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3
S=/c/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad
a() { printf '%x' $((0x270914 + $1 * 0x50 + $2)); }
halt() {
  for n in 1 2 3 4 5 6; do
    $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
    $H mem dump --instance $I --selector 0170 --linear 1efa45 --bytecount 4 --out $D/chk.bin >/dev/null 2>&1
    p=$(python -c "print(open('$D/chk.bin','rb').read().hex())")
    case "$p" in 14092700*) return 0;; esac
    $H resume --instance $I >/dev/null 2>&1; sleep 2
  done
}
halt
for i in $(seq 1 19); do $H debugger-cmd --instance $I "SM 0170:$(a $i 5) 80" >/dev/null 2>&1; sleep 0.25; done
$H debugger-cmd --instance $I "SM 0170:$(a 0 5) 00" >/dev/null 2>&1; sleep 0.25
for i in 0 1; do $H debugger-cmd --instance $I "SM 0170:$(a $i 0x4a) e7 03" >/dev/null 2>&1; sleep 0.25; done
$H resume --instance $I >/dev/null 2>&1; sleep 2
# 只剩索爾未行動:Escape 跳到索爾、移一格(方向由 DIR 決定)、休息
$H key --instance $I --wait 1.5 Escape >/dev/null 2>&1
$H key --instance $I --wait 1.5 Return >/dev/null 2>&1
$H key --instance $I --wait 0.8 ${DIR:-Up} >/dev/null 2>&1
$H key --instance $I --wait 3 Return >/dev/null 2>&1
sleep 2
$H screenshot --instance $I --out $D/${tag}_ring.png >/dev/null 2>&1
$H key --instance $I --wait 1.3 Down >/dev/null 2>&1
$H key --instance $I --wait 2.5 Return >/dev/null 2>&1
sleep 30
python -X utf8 -c "
import sys,time; sys.path.insert(0,'tools'); import fd2_chapter_sweep as sw
from pathlib import Path
log=[]
print(sw.ensure_battle_hud('$I', Path('$D/shots_$tag'), log, '$tag', max_clears=40))" 2>&1 | tail -1
$H screenshot --instance $I --out $D/${tag}_screen.png >/dev/null 2>&1
halt
bash $S/ev_state.sh $I $D $tag
$H mem dump --instance $I --selector 0170 --linear 1efbeb --bytecount 4 --out $D/${tag}_cnt.bin >/dev/null 2>&1
python -c "print('unit count',open('$D/${tag}_cnt.bin','rb').read()[0])"
$H resume --instance $I >/dev/null 2>&1
