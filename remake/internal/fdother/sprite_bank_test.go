package fdother

import (
	"os"
	"testing"
)

func TestDecodeFDSHAP000SpriteBankFromPlayerArchive(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDSHAP.DAT"
	if _, err := os.Stat(datPath); os.IsNotExist(err) {
		t.Skip("player-provided FDSHAP.DAT is absent")
	}
	bank, err := DecodeSpriteBankResource(datPath, 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(bank.Sprites) != 288 {
		t.Fatalf("FDSHAP#0 sprite count=%d, want 288", len(bank.Sprites))
	}
}

func TestDecodeMapTerrainResourcesPairsFDSHAPMapZero(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDSHAP.DAT"
	if _, err := os.Stat(datPath); os.IsNotExist(err) {
		t.Skip("player-provided FDSHAP.DAT is absent")
	}
	bank, controls, err := DecodeMapTerrainResources(datPath, 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(bank.Sprites) != 288 || len(controls) != 1200 {
		t.Fatalf("map0 image/control=%d/%d, want 288/1200", len(bank.Sprites), len(controls))
	}
	if _, _, err := DecodeMapTerrainResources(datPath, -1); err == nil {
		t.Fatal("negative map index accepted")
	}
}
