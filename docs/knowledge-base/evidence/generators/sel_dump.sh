#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 停在 collect_targets_in_range 返回點 0x1b09f0 時傾印堆疊(計數、返回位址、6 個參數)、地圖、單位與 outBuf。
# 用法:sel_dump.sh <標籤>。不 resume。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/sel
tag=$1
p=$(wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p)
eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
echo "$eip $esp last='$(echo "$p" | tail -1)'"
[ "$eip" = "EIP=001B09F0" ] || { echo "not at collect return"; exit 1; }
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
dump $(printf '%x' $((0x${esp#ESP=}))) 40 $D/${tag}_stack.bin
dump 21934c 8e0 $D/${tag}_map.bin
dump 26bdc8 690 $D/${tag}_units.bin
dump 1f3a9e 7 $D/${tag}_sp23.bin
o=$(python -X utf8 -c "import struct;print('%x'%struct.unpack_from('<I',open(r'$D/${tag}_stack.bin','rb').read(),0x20)[0])")
if [ "$o" != "0" ]; then dump "$o" 20 $D/${tag}_out.bin; fi
python -X utf8 -c "
import struct
s=open(r'$D/${tag}_stack.bin','rb').read()
c,=struct.unpack_from('<I',s,0); r,x,y,o,rg,th,se=struct.unpack_from('<7I',s,0x14)
print('count',c,'ret %x'%r,'static %x'%(r-0x19c000),'origin',(x,y),'out %x'%o,'range',rg,'thr',th,'sel',se)
import os
f=r'$D/${tag}_out.bin'
print('out', list(open(f,'rb').read()[:c]) if os.path.exists(f) else None)"
