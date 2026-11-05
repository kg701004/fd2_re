#!/bin/bash
# 續一百四十五:原版 FD2.EXE 開場「金鎖(ANI #0)之後」連拍。使用者 2026-10-21 核准一次 DOSBox-X 連拍。
# 時段依 doc39 §10.5 觸發表:esi==0x19 播 ANI #0(96 幀,續一百四十一拍到第 21 幀 @ t0+44.08)→ esi 24→0 捲動
# → esi==10 的 0x1f73f(FDOTHER 0x4c/0x4b)→ esi==0 停留 1000ms → 擦除轉場 → 標題 #7 + ANI #1。
# 用法:burst_s145.sh <label> <開始秒數(相對 STATUS=running)> <持續秒數>
# 不送任何按鍵;只讀畫面。ts 在 import 前後各取一次,檔名用前者,後者記進 times.txt。
name=s145t
label=$1; start_at=$2; dur=$3
sf=$HOME/.fd2-harness/instances/$name.state
out=$HOME/s145/shots_$label
rm -rf "$out"; mkdir -p "$out"
for i in $(seq 1 120); do
    grep -q '^STATUS=running' "$sf" 2>/dev/null && break
    sleep 0.2
done
grep -q '^STATUS=running' "$sf" || { echo "instance not running"; exit 1; }
t0=$(date +%s.%N)
port=$(sed -n 's/^DISPLAY_PORT=//p' "$sf")
echo "t0=$t0 port=$port" | tee "$out/times.txt"
sleep "$start_at"
end=$(echo "$(date +%s.%N) + $dur" | bc)
n=0
while (( $(echo "$(date +%s.%N) < $end" | bc) )); do
    ts=$(date +%s.%N)
    rel=$(printf '%06.2f' "$(echo "$ts - $t0" | bc)")
    DISPLAY="127.0.0.1:$port" import -window root "$out/shot_${rel}.png" 2>/dev/null
    te=$(date +%s.%N)
    echo "shot_${rel}.png $(echo "$ts - $t0" | bc) $(echo "$te - $t0" | bc)" >> "$out/times.txt"
    n=$((n + 1))
done
echo "shots=$n dir=$out"
