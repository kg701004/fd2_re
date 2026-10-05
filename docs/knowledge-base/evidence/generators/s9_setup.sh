#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 法術 9(咒殺)呈現分流受控場景。前提:除錯器暫停中、玩家回合。
# 用法:s9_setup.sh <[0x53af9] 值> <標籤>
# 悠妮 #1 已學法術改成 [8,9,12,25,32..35](清單第二項 = 法術 9),HP 999/999;盜賊 #11 搬到 (23,19)(距悠妮 3,索爾 8),
# 只會法術 9、MP 100、拿掉武器、HP 999/999;#12 在 (21,14) 當索爾的攻擊對象;其他敵人與 NPC 設 +5 bit0。
# 斷點(執行期 +0x19c000):ai_spell_execute、spell_cast_scene 0x2ff01、玩家/handler 0x214ad、spell_damage_resolve、0x1c7fe、0x1c87f。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
flag=$1; tag=$2
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
cmds=(
  "SM 0170:1efaf9 $(printf '%02x' $flag)"
  "SM 0170:$(a 0 5) 00" "SM 0170:$(a 1 5) 00"
  "SM 0170:$(a 1 0x1a) 00 13 00 02 0f" "SM 0170:$(a 1 0x40) e7 03 e7 03"
  "SM 0170:$(a 11 0) 17 13" "SM 0170:$(a 11 5) 00" "SM 0170:$(a 11 0xa) 00"
  "SM 0170:$(a 11 0x1a) 00 02 00 00 00" "SM 0170:$(a 11 0x44) 64 00 64 00" "SM 0170:$(a 11 0x40) e7 03 e7 03"
  "SM 0170:$(a 12 0) 15 0e" "SM 0170:$(a 12 0x26) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03"
)
# NPC #5、#6 保留(全部 NPC 設 bit0 時,玩家行動後遊戲直接回到標題畫面)
for i in 7 8 9 10 13 14 15 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b1311" "BP 0170:1cbf01" "BP 0170:1bd4ad" "BP 0170:1b875e" "BP 0170:1b87fe" "BP 0170:1b887f")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.7
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/s9_pre_$tag.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 1efaf9 --bytecount 1 --out .wsl_build/ctr/s9_flag_$tag.bin >/dev/null 2>&1
echo "setup done $tag flag=$(od -An -tu1 .wsl_build/ctr/s9_flag_$tag.bin | tr -d ' ')"
