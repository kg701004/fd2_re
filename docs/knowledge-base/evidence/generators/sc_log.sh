#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 法術評分斷點記錄迴圈:每次停下依 EIP 傾印所需資料再 resume,直到窗格末行連續 IDLE 次 "(Running)"。
# 0x1598a 入口:印 (unit, mode),unit 11 時傾印全部單位;0x15add:EAX = 分數,傾印 0x70 bytes 堆疊
# (法術、目標數、目標索引、施放點);0x15b6d:傾印 0x74 bytes 堆疊(unit)與 [0x53c23..0x53c2f];0x15311:印引數。
# 用法:IDLE=<次> sc_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
idle=0
for n in $(seq 1 120); do
  sleep 3
  p=$(pane)
  if echo "$p" | tail -1 | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge $IDLE ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
  eax=$(echo "$p" | grep -o "EAX=[0-9A-F]*" | head -1)
  sp=$(printf '%x' $((0x${esp#ESP=})))
  case "$eip" in
    EIP=001B198A)
      $H mem dump --instance $I --selector 0170 --linear "$sp" --bytecount c --out $D/sc_stk.bin >/dev/null 2>&1
      st=$(python -X utf8 -c "
import struct
r,u,m=struct.unpack('<III',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/sc_stk.bin','rb').read()[:12])
print('ret=%#x unit=%d mode=%d'%(r-0x19c000,u,m))")
      echo "stop $n: entry 0x1598a $st"
      case "$st" in *"unit=11 "*)
        $H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/sc_units_${tag}_$n.bin >/dev/null 2>&1
        echo "  units -> sc_units_${tag}_$n.bin";;
      esac;;
    EIP=001B1ADD)
      $H mem dump --instance $I --selector 0170 --linear "$sp" --bytecount 70 --out $D/sc_call_${tag}_$n.bin >/dev/null 2>&1
      st=$(python -X utf8 -c "
import struct
b=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/sc_call_${tag}_$n.bin','rb').read()
s,c,p=struct.unpack_from('<III',b,0)
print('spell=%d count=%d ptr_ok=%s targets=%s cast=(%d,%d)'%(s,c,p==0x$sp+0xc,list(b[0xc:0xc+c]),b[0x60],b[0x58]))")
      echo "stop $n: score $eax $st";;
    EIP=001B1B6D)
      $H mem dump --instance $I --selector 0170 --linear "$sp" --bytecount 74 --out $D/sc_stk.bin >/dev/null 2>&1
      $H mem dump --instance $I --selector 0170 --linear 1efc23 --bytecount 10 --out $D/sc_best_${tag}_$n.bin >/dev/null 2>&1
      st=$(python -X utf8 -c "
import struct
u=struct.unpack_from('<I',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/sc_stk.bin','rb').read(),0x6c)[0]
print('unit=%d best(score,x,y,spell)=%s'%(u,struct.unpack('<iiii',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/sc_best_${tag}_$n.bin','rb').read()[:16])))")
      echo "stop $n: exit 0x1598a $st";;
    EIP=001B1311)
      $H mem dump --instance $I --selector 0170 --linear "$sp" --bytecount c --out $D/sc_stk.bin >/dev/null 2>&1
      st=$(python -X utf8 -c "
import struct
r,u,m=struct.unpack('<III',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/sc_stk.bin','rb').read()[:12])
print('ret=%#x unit=%d a2=%d'%(r-0x19c000,u,m))")
      echo "stop $n: ai_spell_execute $st";;
    *) echo "stop $n: other $eip";;
  esac
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
