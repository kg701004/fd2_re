#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 推進升級對話:每次按 Return,若停在斷點就記錄 EBP(成長量)與屬性指標後繼續;每步截圖。
# 用法:dlg_step.sh <標籤> <步數>
# 前提:遊戲執行中(非暫停),斷點 0x1ba55a 已設。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
tag=$1; steps=$2
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
drain() {
  for m in 1 2 3 4 5 6 7 8; do
    sleep 2
    p=$(pane)
    echo "$p" | tail -1 | grep -q "Running" && return 0
    eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
    ebp=$(echo "$p" | grep -o "EBP=[0-9A-F]*" | head -1)
    esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
    a=$(printf '%x' $((0x${esp#ESP=} + 0x14)))
    $H mem dump --instance $I --selector 0170 --linear "$a" --bytecount 10 --out .wsl_build/ctr/stk_$tag.bin >/dev/null 2>&1
    st=$(python -X utf8 -c "import struct;b=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/stk_$tag.bin','rb').read();s,g,msg,i=struct.unpack('<4I',b[:16]);print('stat_ptr=%#x (unit+%#x) growth_ptr=%#x msg=%#x idx=%d'%(s,(s-0x26bdc8)%0x50,g,msg,i))")
    echo "  stop: $eip gain(EBP)=$((0x${ebp#EBP=})) $st"
    $H resume --instance $I >/dev/null 2>&1
  done
}
drain
for n in $(seq 1 "$steps"); do
  $H key --instance $I --wait 1.0 Return >/dev/null 2>&1
  echo "step $n: Return"
  drain
  $H screenshot --instance $I --out .wsl_build/ctr/${tag}_d$n.png >/dev/null 2>&1
done
