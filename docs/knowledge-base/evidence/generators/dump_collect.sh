#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 除錯器停在 collect_targets_in_range 返回點(0x1b09f0)時:依畫面上的 ESP 傾印堆疊/地圖/單位/outBuf 並離線重算。
# 用法:dump_collect.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
tag=$1
D=.wsl_build/ctr
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
p=$(wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p)
eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
echo "$eip $esp $(echo "$p" | tail -1)"
[ "$eip" = "EIP=001B09F0" ] || { echo "not at collect return"; exit 1; }
e=$(printf '%x' $((0x${esp#ESP=})))
$H mem dump --instance $I --selector 0170 --linear "$e" --bytecount 40 --out $D/${tag}_stack.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 21934c --bytecount 8e0 --out $D/${tag}_map.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/${tag}_units.bin >/dev/null 2>&1
o=$(python -X utf8 -c "import struct;print('%x'%struct.unpack_from('<I',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/${tag}_stack.bin','rb').read(),0x20)[0])")
$H mem dump --instance $I --selector 0170 --linear "$o" --bytecount 20 --out $D/${tag}_out.bin >/dev/null 2>&1
python -X utf8 "$S/collect_check.py" $D/${tag}_stack.bin $D/${tag}_map.bin $D/${tag}_units.bin $D/${tag}_out.bin
