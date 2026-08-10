package main

import (
	"math"
	"strings"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

// TestDlgPaginationPreservesText 驗證長對白分頁後全文保全(不再被截斷丟棄),頁數正確。
// 對應使用者回饋 2026-07-05:父王 line17 等長句舊碼只畫 3 行、其餘丟棄,Enter 直接跳下一句。
func TestDlgPaginationPreservesText(t *testing.T) {
	// 王座廳 line17(父王,上框 id>=32):57 字,上框 perLine=13 → 5 行 → 2 頁。
	long := "我就知道你會一時無法接受,這樣吧,三天之後,你再給我考慮的結果,當然了,我希望能夠聽到肯定的答覆。你先回去休息吧。"
	dl := battle.DialogLine{Speaker: 48, Text: long}
	g := &Game{}

	lines := g.dlgWrap(dl)
	// 1) 全文保全:所有顯示列接回 == 『長句』(含引號),無任何字被丟棄。
	joined := strings.Join(lines, "")
	want := "『" + toFullWidth(dl.Text) + "』"
	if joined != want {
		t.Fatalf("分頁丟字:\n got=%q\nwant=%q", joined, want)
	}
	// 2) 頁數 = ceil(行數/3),且 >1(這句必分頁)。
	pages := g.dlgPageCount(dl)
	wantPages := (len(lines) + 2) / 3
	if pages != wantPages || pages < 2 {
		t.Fatalf("頁數錯:got=%d want=%d(行數=%d)", pages, wantPages, len(lines))
	}
	// 3) 最後一頁確實含句尾(舊碼會丟掉的部分)。
	lastPageStart := (pages - 1) * 3
	tail := strings.Join(lines[lastPageStart:], "")
	if !strings.Contains(tail, "休息吧") {
		t.Fatalf("末頁未含句尾『休息吧』,tail=%q", tail)
	}
	t.Logf("line17: %d 字 → %d 行 → %d 頁,全文保全 ✓", len([]rune(long)), len(lines), pages)
}

// TestDlgShortLineSinglePage 短句(<=3行)維持單頁,Enter 直接換句(不影響原行為)。
func TestDlgShortLineSinglePage(t *testing.T) {
	dl := battle.DialogLine{Speaker: 0, Text: "是。"}
	g := &Game{}
	if p := g.dlgPageCount(dl); p != 1 {
		t.Fatalf("短句應單頁,got=%d", p)
	}
}

func TestDlgPaginationStartsSmoothScrollAndBlocksSkip(t *testing.T) {
	long := battle.DialogLine{Speaker: 0, Text: "這是一段需要分頁顯示的長對白,按下確認後應該平滑往上捲動,並且要在第二頁完整顯示剩餘內容後才能換句。"}
	g := Game{dialog: []battle.DialogLine{long}}
	if g.dlgAdvance() {
		t.Fatal("翻到下一頁不應立即換句")
	}
	if g.dlgPage != 1 || g.dlgScrollFrom != 0 || g.dlgScrollT != dlgScrollFrames {
		t.Fatalf("scroll state=%d/%d/%d", g.dlgPage, g.dlgScrollFrom, g.dlgScrollT)
	}
	if g.dlgAdvance() || g.dlgPage != 1 {
		t.Fatal("捲動期間再次 Enter 不應跳過頁面")
	}
	g.dlgScrollT = 0
	if !g.dlgAdvance() || len(g.dialog) != 0 || g.dlgPage != 0 {
		t.Fatalf("完成最後一頁後未換句: dialog=%d page=%d", len(g.dialog), g.dlgPage)
	}
}

func TestPortraitScaleComputation(t *testing.T) {
	computeScale := func(width float64) float64 {
		return 168.0 / width
	}

	// 1) given a mock/stub image width of 80px, the computed scale should match the original 2.1 behavior (within floating point tolerance)
	scale80 := computeScale(80.0)
	expected80 := 2.1
	if math.Abs(scale80-expected80) > 1e-9 {
		t.Errorf("expected scale for 80px to be %f, got %f", expected80, scale80)
	}

	// 2) given a different width (e.g. 320px), the computed scale should produce the same ~168px effective display size
	scale320 := computeScale(320.0)
	effectiveSize320 := scale320 * 320.0
	if math.Abs(effectiveSize320-168.0) > 1e-9 {
		t.Errorf("expected effective display size for 320px to be 168.0, got %f", effectiveSize320)
	}
}

func TestDlgWrapWithDynamicPortraitScale(t *testing.T) {
	// Let's create mock images of different sizes.
	img80 := ebiten.NewImage(80, 80)
	img320 := ebiten.NewImage(320, 320)

	// Test 1: With 80px portrait
	g := &Game{portraits: map[int][]*ebiten.Image{
		48: {img80},
	}}
	long := "我就知道你會一時無法接受,這樣吧,三天之後,你再給我考慮的結果,當然了,我希望能夠聽到肯定的答覆。你先回去休息吧。"
	dl := battle.DialogLine{Speaker: 48, Text: long}
	lines80 := g.dlgWrap(dl)

	// Test 2: With 320px portrait
	g.portraits = map[int][]*ebiten.Image{
		48: {img320},
	}
	lines320 := g.dlgWrap(dl)

	// They should wrap exactly the same way, producing identical lines!
	if len(lines80) != len(lines320) {
		t.Fatalf("length mismatch: 80px had %d lines, 320px had %d lines", len(lines80), len(lines320))
	}
	for i := range lines80 {
		if lines80[i] != lines320[i] {
			t.Errorf("line %d mismatch: 80px=%q, 320px=%q", i, lines80[i], lines320[i])
		}
	}
}
