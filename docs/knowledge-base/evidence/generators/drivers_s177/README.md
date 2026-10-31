# 探針(續一百七十七)

使用者 2026-10-31「先完善優化工具」。沒有實機;只讀 `.wsl_build/lc17*_live/` 既有的呼叫紀錄。

| 檔 | 用途 |
|---|---|
| `equiv_episodes.py` | `verify_selftest_discrimination.py --exhaustive --tool calllog_segments.py` 最後剩下的 `cmd_episodes` int 0->1(`key[0] is None` 改 `key[1] is None`)是否等價:7 份 DOSBox-X 呼叫紀錄(lc171a .. lc174b)、216544 個完整 episode 的鍵沒有 None,突變版輸出 7 / 7 與原版逐位元組相同,對照突變(f-string 改印 key[1])7 / 7 不同(登錄進 `docs/data/equivalent_mutants.json` 的依據) |

當時的步驟:selftest 加 CLI 測試後 `main()` 第一次在 selftest 裡被跑到,原本到不了的 `cmd_episodes` / `cmd_disasm` / 各子命令選項
變成可達、逃掉 13 → 12 → 5 個;補 episodes / disasm 全輸出(手算)、`field_at` 1 位元組、新形式 A、R / A 計數不對稱、
stderr 提示之後剩這一個,探針證明等價後登錄。
