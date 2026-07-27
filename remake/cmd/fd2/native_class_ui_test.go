package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestDrawNativeClassListUsesPlayerOriginalAssets(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(base, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)
	assets, err := loadNativeClassUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	special := 0x34
	g := &Game{
		nativeClassUI: assets,
		churchMode:    "class",
		churchIDs:     []int{9},
		partyRoster: map[int]battle.Unit{9: {
			Name: "悠妮", Portrait: 9, ClassID: 5,
			NativeIdentity: 9, HasNativeIdentity: true,
			MapSelectorKey: 9, HasMapSelectorKey: true,
			Inventory: []int{0x5a},
		}},
		classChangeTable: campaign.ClassChangeTable{
			Current: map[int]campaign.ClassChangeCurrent{9: {
				Portrait: 9, DefaultTarget: 0x29, SpecialItem: 0x5a, SpecialTarget: &special,
			}},
			Targets: map[int]campaign.ClassChangeTarget{
				0x29: {Portrait: 0x29, ClassID: 13},
				0x34: {Portrait: 0x34, ClassID: 21},
			},
		},
	}
	screen := ebiten.NewImage(640, 400)
	if !g.drawNativeClassList(screen) {
		t.Fatal("native class list unexpectedly fell back")
	}
}
