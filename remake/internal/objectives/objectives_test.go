package objectives

import "testing"

// TestChaptersCoverAllThirty checks the table has exactly the 30 walkthrough
// chapters, numbered 1..30 with no gaps or duplicates, matching doc28 §2's
// stated chapter count (30, aligned with battle_events.json).
func TestChaptersCoverAllThirty(t *testing.T) {
	if got := len(Chapters); got != 30 {
		t.Fatalf("len(Chapters) = %d, want 30", got)
	}
	seen := make(map[int]bool, 30)
	for i, c := range Chapters {
		if c.Number != i+1 {
			t.Errorf("Chapters[%d].Number = %d, want %d (table must stay in walkthrough order)", i, c.Number, i+1)
		}
		if seen[c.Number] {
			t.Errorf("duplicate chapter number %d", c.Number)
		}
		seen[c.Number] = true
	}
	for n := 1; n <= 30; n++ {
		if !seen[n] {
			t.Errorf("missing chapter number %d", n)
		}
	}
}

// TestChaptersHaveRequiredFields checks every chapter has a non-empty title
// and win condition, and that every recruit/guard entry has a non-empty name
// (empty Who/GuardTargets entries would silently render as blank UI rows).
func TestChaptersHaveRequiredFields(t *testing.T) {
	for _, c := range Chapters {
		if c.Title == "" {
			t.Errorf("chapter %d: empty Title", c.Number)
		}
		if c.WinCondition == "" {
			t.Errorf("chapter %d: empty WinCondition", c.Number)
		}
		for i, g := range c.GuardTargets {
			if g == "" {
				t.Errorf("chapter %d: GuardTargets[%d] is empty", c.Number, i)
			}
		}
		for i, r := range c.Recruits {
			if r.Who == "" {
				t.Errorf("chapter %d: Recruits[%d].Who is empty", c.Number, i)
			}
		}
	}
}

// TestByNumber spot-checks a few entries transcribed directly from
// doc28 §2, including the first, a middle chapter with every field
// populated (guard + conditioned recruit), and the last chapter.
func TestByNumber(t *testing.T) {
	c, ok := ByNumber(1)
	if !ok {
		t.Fatal("ByNumber(1) not found")
	}
	if c.Title != "初試身手" || c.WinCondition != "敵全滅" {
		t.Errorf("chapter 1 = %+v, want title=初試身手 win=敵全滅", c)
	}
	if len(c.Recruits) != 1 || c.Recruits[0].Who != "哈諾" || c.Recruits[0].Condition != "出現前勿滅完" {
		t.Errorf("chapter 1 Recruits = %+v, want [{哈諾 出現前勿滅完}]", c.Recruits)
	}

	c16, ok := ByNumber(16)
	if !ok {
		t.Fatal("ByNumber(16) not found")
	}
	if len(c16.GuardTargets) != 1 || c16.GuardTargets[0] != "蜜蒂" {
		t.Errorf("chapter 16 GuardTargets = %v, want [蜜蒂]", c16.GuardTargets)
	}
	if len(c16.Recruits) != 1 || c16.Recruits[0].Condition != "HP320以上／18回合內／部下陣亡未過半" {
		t.Errorf("chapter 16 Recruits = %+v, unexpected condition text", c16.Recruits)
	}

	c30, ok := ByNumber(30)
	if !ok {
		t.Fatal("ByNumber(30) not found")
	}
	if c30.Title != "傳說的終章" || c30.WinCondition != "空魔神死亡" {
		t.Errorf("chapter 30 = %+v, want title=傳說的終章 win=空魔神死亡", c30)
	}

	if _, ok := ByNumber(0); ok {
		t.Error("ByNumber(0) should not be found (chapters are 1-based)")
	}
	if _, ok := ByNumber(31); ok {
		t.Error("ByNumber(31) should not be found (only 30 chapters)")
	}
}
