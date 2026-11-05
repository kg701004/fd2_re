#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 恢復術(法術 13)評分受控場景。前提:除錯器暫停中、玩家回合。
# 用法:hl_setup.sh <標籤> <目標規格...>(序號:x:y:HP:bit0,見 hl_gen.py)
# 盜賊 #11 在 (13,18),只會法術 13(回復 70、距離 4、範圍 0、MP 3、選擇子 1 → 評分時取己方),MP 100、HP 滿、拿掉武器;
# NPC #5/#6 搬到左上角 (1,1)/(2,1),#7..#10 與未列出的敵人設 +5 bit0;#12 在 (21,14) 當索爾的攻擊對象;隊員 #1..#4 設已行動。
# 斷點(執行期 +0x19c000):0x1598a 入口、0x15add、0x15b6d、0x15311。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
tag=$1; shift
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/hl_raw_$tag.bin >/dev/null 2>&1
cmds=(
  "SM 0170:$(a 0 5) 00" "SM 0170:$(a 1 5) 80" "SM 0170:$(a 2 5) 80" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 4 5) 80"
  "SM 0170:$(a 5 0) 01 01" "SM 0170:$(a 6 0) 02 01"
  "SM 0170:$(a 11 0) 0d 12" "SM 0170:$(a 11 5) 00" "SM 0170:$(a 11 0xa) 00"
  "SM 0170:$(a 11 0x1a) 00 20 00 00 00" "SM 0170:$(a 11 0x44) 64 00 64 00" "SM 0170:$(a 11 0x40) 1c 00"
  "SM 0170:$(a 12 0) 15 0e" "SM 0170:$(a 12 0x26) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03"
)
listed=" $(for s in "$@"; do echo -n "${s%%:*} "; done)"
for i in 7 8 9 10 13 14 15 16 17 18 19 20; do
  case "$listed" in *" $i "*) ;; *) cmds+=("SM 0170:$(a $i 5) 01");; esac
done
while IFS= read -r c; do cmds+=("$c"); done < <(python -X utf8 "$S/hl_gen.py" "C:/Users/kg701/Desktop/GAME/fd2_re/$D/hl_raw_$tag.bin" "$@" | tr -d '\r')
cmds+=("BP 0170:1b198a" "BP 0170:1b1add" "BP 0170:1b1b6d" "BP 0170:1b1311")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.6
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/hl_pre_$tag.bin >/dev/null 2>&1
echo "setup done $tag"
