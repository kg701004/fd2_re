#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 施法後 [0x53ec8] 歸 0 的檢查:沿用 sc_setup.sh 的場景(R4 條件),盜賊 EX 設 0,
# 斷點 0x1546a(寫 0 之前)與 0x15474(寫 0 之後),各讀 [0x53ec8](執行期 0x1efec8)。前提:除錯器暫停中、玩家回合。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
tag=${1:-r5}
RACES="1:1 2:4 3:1 4:1" bash "$S/sc_setup.sh" 440 440 79 $tag
# EXTRA="SM ...;SM ..." 追加的記憶體寫入(例如把 NPC 搬進射程)
IFS=';' read -ra X <<< "${EXTRA:-}"
for c in "BPDEL *" "SM 0170:26c174 00" "${X[@]}" "BP 0170:1b146a" "BP 0170:1b1474"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.7
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/sc_pre_$tag.bin >/dev/null 2>&1
$H resume --instance $I >/dev/null 2>&1; sleep 2
for k in Return Return Up Return Return; do $H key --instance $I --wait 1.2 $k >/dev/null 2>&1; done
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
idle=0
for n in $(seq 1 60); do
  sleep 3
  p=$(pane)
  if echo "$p" | tail -1 | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge 8 ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  $H mem dump --instance $I --selector 0170 --linear 1efec8 --bytecount 4 --out $D/sc_ec8_$n.bin >/dev/null 2>&1
  v=$(python -X utf8 -c "import struct;print(struct.unpack('<i',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/sc_ec8_$n.bin','rb').read()[:4])[0])")
  echo "stop $n: $eip [0x53ec8]=$v"
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
