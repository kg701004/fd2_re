#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 範圍法術:按下確認後,反覆「等斷點 -> 記錄暫存器 -> resume」直到不再停下。
# BP1 0x1b87fe(0x1c7fe):ESI=base、EDX=命中亂數,目標序號在 [ESP+0x84]
# BP2 0x1b887f(0x1c87f):EDX=傷害亂數,ESI=目標記錄位址
# 用法:bp_loop.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
tag=$1
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
[ -n "${NOKEY:-}" ] || $H key --instance $I --wait 1.5 Return >/dev/null 2>&1
idle=0
for n in $(seq 1 40); do
  sleep 3
  p=$(pane)
  last=$(echo "$p" | tail -1)
  if echo "$last" | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge 6 ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  eax=$(echo "$p" | grep -o "EAX=[0-9A-F]*" | head -1)
  esi=$(echo "$p" | grep -o "ESI=[0-9A-F]*" | head -1)
  edx=$(echo "$p" | grep -o "EDX=[0-9A-F]*" | head -1)
  esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
  tgt=""
  if [ "$eip" = "EIP=001B87FE" ]; then
    a=$(printf '%x' $((0x${esp#ESP=} + 0x84)))
    $H mem dump --instance $I --selector 0170 --linear "$a" --bytecount 8 --out .wsl_build/ctr/stk_$tag.bin >/dev/null 2>&1
    tgt=$(python -X utf8 -c "import struct;b=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/stk_$tag.bin','rb').read();print('target=%d spell=%d'%struct.unpack('<II',b[:8]))")
  fi
  if [ "$eip" = "EIP=001B875E" ] || [ "$eip" = "EIP=001B8916" ]; then
    # 函式入口:[ESP]=返回位址、[ESP+4]=目標、[ESP+8]=法術
    a=$(printf '%x' $((0x${esp#ESP=})))
    $H mem dump --instance $I --selector 0170 --linear "$a" --bytecount c --out .wsl_build/ctr/stk_$tag.bin >/dev/null 2>&1
    tgt=$(python -X utf8 -c "import struct;b=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/stk_$tag.bin','rb').read();print('ENTRY ret=%#x target=%d spell=%d'%struct.unpack('<III',b[:12]))")
  fi
  edi=$(echo "$p" | grep -o "EDI=[0-9A-F]*" | head -1)
  ebp=$(echo "$p" | grep -o "EBP=[0-9A-F]*" | head -1)
  echo "stop $n: $eip $ebp $edi $esi $edx $eax $esp $tgt"
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
$H screenshot --instance $I --out .wsl_build/ctr/after_$tag.png >/dev/null 2>&1
for n in 1 2 3 4; do
  $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
  q=$($H mem read-global --instance $I --selector 0170 --ghidra-addr 53a45 --bytecount 4 --delta 19c000 --out-dir .wsl_build/ctr/pp 2>&1 | grep raw)
  case "$q" in *c8bd2600*) break;; esac
  echo "pointer read '$q' (try $n), re-entering"; $H resume --instance $I >/dev/null 2>&1; sleep 2
done
$H debugger-cmd --instance $I "BPDEL *" >/dev/null 2>&1; sleep 1
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/post_$tag.bin >/dev/null 2>&1
python -X utf8 - "$tag" <<'PY'
import struct, sys
b = open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/post_%s.bin' % sys.argv[1], 'rb').read()
for i in range(21):
    r = b[i*80:(i+1)*80]; w = lambda o: struct.unpack_from('<H', r, o)[0]
    print('post', i, (r[0], r[1]), 'side', r[6], 'f5', hex(r[5]), 'race', r[0x1f], 'class', r[0x20], 'HP', w(0x40), 'MP', w(0x44))
PY
