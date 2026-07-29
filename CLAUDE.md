# 目標：炎龍騎士團2 反組譯與重製

> 所有 agent 開工前必須先讀 [`AGENTS.md`](AGENTS.md)。操作鐵則、證據分級、
> Docker 清理、文件權威順序與 commit 政策只在該檔維護，避免兩份指示漂移。

我希望把炎龍騎士團2 remake , 可以在網頁上還有 手機上真的重新玩一次 

1. 從青衫的攻略裡面建立知識庫
2. 用第一性原理方式反組譯 當年的經典 (記住 dq3 犯的錯誤,避免輪迴)
3. 方向：素材拆解 , 繪圖/音樂/規則/邏輯 從程式碼裡面還原
4. 預計用 兩種技術重製
  - sdl2 and c++ 參考 精訊勇者鬥惡龍三 @/home/anr2/dq3
  - golang Go / Ebiten 參考魔法大帝 @/home/anr2/master-of-maigc
5. RE 前要擬定計畫，RE 要徹底；以目前可用的 DOSBox capture、IDA、Ghidra
   與 Docker Capstone 建立可重現證據
6. 研究玩所有資料, 制定計畫  一步一步推進
7. 參考近期的 lesson learning 
8. 每輪整理可 stage；累積成重大且已驗證的更新後才 commit + push GitHub
9. README.md 要突顯貢獻, 圖文並茂

# 炎龍騎士團2 位置
@/home/anr2/cht/fd2/org_game/炎龍騎士團/FLAME2

# github repo 位置
https://github.com/wicanr2/fd2_re.git
