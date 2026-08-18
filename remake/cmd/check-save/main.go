package main

import (
	"fmt"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/fdsave"
)

func main() {
	raw, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	plain, err := fdsave.Decode(raw)
	if err != nil {
		panic(err)
	}
	for slot := 0; slot < fdsave.SlotCount; slot++ {
		md, err := fdsave.ReadVerifiedMetadata(plain, slot)
		if err != nil {
			fmt.Printf("slot %d: error %v\n", slot, err)
			continue
		}
		fmt.Printf("slot %d: Chapter=%d RosterCount=%d Currency=%d\n", slot, md.Chapter, md.RosterCount, md.Currency)
	}
}
