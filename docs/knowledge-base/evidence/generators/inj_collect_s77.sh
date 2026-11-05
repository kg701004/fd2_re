#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十七:注入實驗收尾 —— 把 DOSBox-X 記錄檔(去掉 INT 6 洪水)、HEAVYLOG 的最後指令、tmux 面板存到 Windows 端。
# 用法:inj_collect_s77.sh <instance> <dest_dir(WSL 路徑)>
set -u
name="$1"; dst="$2"
wd="$HOME/fd2-run-harness-$name"
mkdir -p "$dst"
f="$wd/dosbox-x.log"
if [[ -f "$f" ]]; then
  {
    echo "# total_lines $(wc -l < "$f")  int6_lines $(grep -c 'Unhandled Interrupt Called 6' "$f")"
    grep -n -v -e 'Unhandled Interrupt Called 6' -e 'to rom at lin=' "$f" | tail -60
  } > "$dst/dosbox-x_log_excerpt.txt"
else
  echo "# no dosbox-x.log" > "$dst/dosbox-x_log_excerpt.txt"
fi
if [[ -f "$wd/LOGCPU_INT_CD.TXT" ]]; then
  { echo "# lines $(wc -l < "$wd/LOGCPU_INT_CD.TXT")"; tail -80 "$wd/LOGCPU_INT_CD.TXT"; } > "$dst/heavylog_tail.txt"
else
  echo "# no LOGCPU_INT_CD.TXT" > "$dst/heavylog_tail.txt"
fi
tmux -L fd2harness capture-pane -t "harness-$name" -p > "$dst/pane.txt" 2>/dev/null || echo "# no pane" > "$dst/pane.txt"
ls -la "$dst"
