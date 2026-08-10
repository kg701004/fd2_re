// export-figani-meta 從玩家自備的 FIGANI.DAT 重新產生
// remake/assets/figani/meta.json——0x2935b 執行期用的逐幀 (X,Y) 定位資料
// (見 docs/knowledge-base/56-fd2-remake-sdd.md「FIGANI placement bridge」)。
//
// 每一筆都是直接用 internal/figani.DecodeResource 解出來的,跟
// cmd/fd2/figmeta_test.go 拿來交叉驗證 meta.json 的程式碼完全同一份,兩邊
// 不可能悄悄跑偏。資產屬版權,只在本機用,見根目錄 .gitignore(org_game/)。
//
// 用法:
//
//	go run ./cmd/export-figani-meta <FIGANI.DAT 路徑> <輸出 meta.json 路徑>
//
// 例:
//
//	go run ./cmd/export-figani-meta \
//	  "../org_game/炎龍騎士團/FLAME2/FIGANI.DAT" assets/figani/meta.json
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"

	"github.com/wicanr2/fd2_re/remake/internal/figani"
)

// maxProbedResource 涵蓋已知全 FIGANI.DAT 264 個動畫(doc06)還留餘裕;解不出
// 來的索引直接跳過,不當錯誤(FIGANI.DAT 本身就不是每個索引都有效資源)。
const maxProbedResource = 320

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: export-figani-meta <FIGANI.DAT path> <out meta.json path>")
		os.Exit(1)
	}
	archivePath, outPath := os.Args[1], os.Args[2]

	meta := map[string][][2]int{}
	for resource := 0; resource < maxProbedResource; resource++ {
		animation, err := figani.DecodeResource(archivePath, resource)
		if err != nil {
			continue
		}
		positions := make([][2]int, len(animation.Frames))
		for i, frame := range animation.Frames {
			positions[i] = [2]int{frame.X, frame.Y}
		}
		meta[strconv.Itoa(resource)] = positions
	}
	if len(meta) == 0 {
		fmt.Fprintln(os.Stderr, "no FIGANI resources decoded; check the archive path")
		os.Exit(1)
	}

	raw, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile(outPath, raw, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	keys := make([]int, 0, len(meta))
	for k := range meta {
		n, _ := strconv.Atoi(k)
		keys = append(keys, n)
	}
	sort.Ints(keys)
	fmt.Printf("wrote %s (%d resources: %v)\n", outPath, len(meta), keys)
}
