#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十六:每份 LOGL 追蹤裡,每次計時器 IRQ 進 0070:42D1 時的 EDI(blit 寫入前緣),
# 以及這次出差有沒有走 0070:0477 jmp 0018:092C(切回實際模式)。輸出:<run>.irq.tsv
#   欄位:行號  EDI  是否切實際模式(1/0)
out_dir="$1"; shift
for v in "$@"; do
  f="$HOME/fd2-run-harness-$v/LOGCPU.TXT"
  awk '
    / 0070:000042D1 / { if (n) print ln "\t" edi "\t" rm; i = index($0, "EDI:"); edi = substr($0, i + 4, 8); ln = NR; rm = 0; n = 1 }
    / 0070:00000477 +jmp +0018:/ { rm = 1 }
    END { if (n) print ln "\t" edi "\t" rm }
  ' "$f" > "$out_dir/$v.irq.tsv"
  echo "$v $(wc -l < "$out_dir/$v.irq.tsv") irq, $(awk '$3==1' "$out_dir/$v.irq.tsv" | wc -l) to real mode"
done
