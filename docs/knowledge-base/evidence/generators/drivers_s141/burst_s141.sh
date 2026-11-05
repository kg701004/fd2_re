#!/bin/bash
# 存檔(續一百四十二):續一百四十一在 WSL ~/s141/ 執行的那一版(b、c 兩段;a 段用的是更早寫到 /tmp 的版本,只差輸出目錄),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續一百四十一:原版 FD2.EXE 開場分鏡⑨(惡魔臉)短連拍。使用者核准:一小段(約 2–3 秒)連拍。
# 用法:burst_s141.sh <label> <開始秒數(相對 DOSBox 視窗出現)> <持續秒數>
# 不送任何按鍵;只讀畫面。
name=s141t
label=$1; start_at=$2; dur=$3
sf=$HOME/.fd2-harness/instances/$name.state
out=/home/kg701004/s141/shots_$label
rm -rf "$out"; mkdir -p "$out"
for i in $(seq 1 90); do
    grep -q '^STATUS=running' "$sf" 2>/dev/null && break
    sleep 1
done
grep -q '^STATUS=running' "$sf" || { echo "instance not running"; exit 1; }
t0=$(date +%s.%N)
port=$(sed -n 's/^DISPLAY_PORT=//p' "$sf")
echo "t0=$t0 port=$port"
sleep "$start_at"
end=$(echo "$(date +%s.%N) + $dur" | bc)
n=0
while (( $(echo "$(date +%s.%N) < $end" | bc) )); do
    ts=$(date +%s.%N)
    rel=$(printf '%06.2f' "$(echo "$ts - $t0" | bc)")
    DISPLAY="127.0.0.1:$port" import -window root "$out/shot_${rel}.png" 2>/dev/null
    n=$((n + 1))
done
echo "shots=$n dir=$out"
ls "$out" | head -40
