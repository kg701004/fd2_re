#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:讀 map 28 事件狀態 —— [0x53ad5] 戰場區域狀態(0x20 bytes)、[0x53a55] 控制段(前 0x54 bytes:3 + 16×3 回合列 + 格子事件表)、
# 回合 [0x53bef]、單位表。前提:除錯器以保護模式停住。
# 用法:ev_state.sh <instance> <out_dir> <tag>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
dump 1efad5 4 $D/${tag}_pad5.bin; dump 1efa55 4 $D/${tag}_pa55.bin; dump 1efbef 4 $D/${tag}_turn.bin
read PAD5 PA55 < <(python -X utf8 -c "
import struct
r=lambda f: struct.unpack('<I',open(r'$D/${tag}_'+f+'.bin','rb').read())[0]
print('%x %x'%(r('pad5'),r('pa55')))" | tr -d '\r')
dump $PAD5 20 $D/${tag}_ad5.bin; dump $PA55 54 $D/${tag}_ctl.bin; dump 270914 17c0 $D/${tag}_units.bin
python -X utf8 -c "
import struct
a=open(r'$D/${tag}_ad5.bin','rb').read(); c=open(r'$D/${tag}_ctl.bin','rb').read(); t=open(r'$D/${tag}_turn.bin','rb').read()[0]
u=open(r'$D/${tag}_units.bin','rb').read()
print('turn',t,'ad5=$PAD5 +0x10',a[0x10],'+0x11',a[0x11],'+0x15',a[0x15],'| rows',[(c[3+3*k],c[4+3*k],c[5+3*k]) for k in range(4)])
for i in range(len(u)//80):
    r=u[i*80:i*80+80]
    if r[7] in (0x68,0x7f,0x69,0x7e) or i==1: print('  unit',i,(r[0],r[1]),'f5',hex(r[5]),'side',r[6],'+7',hex(r[7]),'+8',r[8],'race',r[0x1f],'cls',r[0x20],'HP',struct.unpack_from('<H',r,0x40)[0])
"
