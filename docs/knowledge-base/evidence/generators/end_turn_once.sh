#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:結束一個回合(sweep 的 confirm_end_turn),等敵我回合跑完並清掉對話,停住後讀事件狀態。
# 用法:end_turn_once.sh <instance> <out_dir> <tag>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3
S=/c/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad
python -X utf8 -c "
import sys; sys.path.insert(0,'tools'); import fd2_chapter_sweep as sw
from pathlib import Path
log=[]; r=sw.confirm_end_turn('$I', Path('$D/shots_$tag'), log); print('engine_code', r.get('engine_code'))
import time; time.sleep(8)
print(sw.ensure_battle_hud('$I', Path('$D/shots_$tag'), log, '$tag', max_clears=40)); print(log[-1])" 2>&1 | tail -3
$H screenshot --instance $I --out $D/${tag}_screen.png >/dev/null 2>&1
for n in 1 2 3 4 5 6; do
  $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
  $H mem dump --instance $I --selector 0170 --linear 1efa45 --bytecount 4 --out $D/chk.bin >/dev/null 2>&1
  p=$(python -c "print(open('$D/chk.bin','rb').read().hex())")
  case "$p" in 14092700*) break;; esac
  $H resume --instance $I >/dev/null 2>&1; sleep 2
done
bash $S/ev_state.sh $I $D $tag
$H resume --instance $I >/dev/null 2>&1
