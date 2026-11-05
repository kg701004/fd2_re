#!/bin/bash
# v2 — 修掉 v1 的兩個自身缺陷(兩個都會製造假 MISS):
#  (a) 命中判定用嚴格等值 `EIP=001AD719`,但斷點命中後 CPU 可能已步過該指令,
#      顯示 `EIP=001AD71C`(+3)。改成比對前綴 `EIP=001AD71`。
#  (b) 判為 MISS 時不 resume,遊戲就一直停在 debugger,之後每一次按鍵都無效,
#      失真連鎖擴散。改成:只要 pane 不是 "(Running)" 就一律 resume。
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 1
export PYTHONIOENCODING=utf-8
H="python tools/fd2_dosbox_live_helper.py"
I="$1"; N="${2:-20}"; KEY="${3:-confirm}"

pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t "harness-$I" -p 2>/dev/null; }
resume_if_halted() {
  if ! pane | tail -2 | grep -q "(Running)"; then $H resume --instance $I >/dev/null 2>&1; fi
}

$H enter-debugger --instance $I >/dev/null 2>&1
$H debugger-cmd --instance $I "BPDEL *" >/dev/null 2>&1
$H debugger-cmd --instance $I "BP 0170:001AD719" >/dev/null 2>&1
$H resume --instance $I >/dev/null 2>&1

ok=0; fail=0
for i in $(seq 1 "$N"); do
  $H key --instance $I confirm --wait 1.6 >/dev/null 2>&1
  $H key --instance $I "$KEY" --wait 2.2 >/dev/null 2>&1
  eip=$(pane | sed -n '3p' | grep -o 'EIP=[0-9A-F]*')
  case "$eip" in
    EIP=001AD71*) ok=$((ok+1));   echo "trial $i: HIT   ($eip)" ;;
    *)            fail=$((fail+1)); echo "trial $i: MISS  ($eip)" ;;
  esac
  resume_if_halted
  $H key --instance $I cancel --wait 1.0 >/dev/null 2>&1
  $H key --instance $I cancel --wait 1.0 >/dev/null 2>&1
  resume_if_halted
done
echo "=== $I / $KEY: 命中 $ok / 未命中 $fail (共 $N 次) ==="
