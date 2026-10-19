#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 清掉 harness 除錯器輸入列(退格),再送 RUN;$1 = instance 名稱
cd /tmp || exit 1
for _ in $(seq 1 40); do
    tmux -L fd2harness send-keys -t "harness-$1" BSpace BSpace BSpace BSpace BSpace BSpace
done
sleep 0.5
tmux -L fd2harness send-keys -t "harness-$1" 'RUN' Enter
sleep 1.5
tmux -L fd2harness capture-pane -t "harness-$1" -p | grep -v '^[[:space:]]*$' | tail -3
