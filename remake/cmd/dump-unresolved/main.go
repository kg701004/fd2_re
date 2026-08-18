package main

import (
	"fmt"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func main() {
	for _, path := range os.Args[1:] {
		script, err := campaign.LoadHandlerScript(path)
		if err != nil {
			fmt.Printf("%s: load error: %v\n", path, err)
			continue
		}
		_, issues := campaign.CompileHandlerScript(script, campaign.HandlerBindings{})
		fmt.Printf("=== %s (%d issues) ===\n", path, len(issues))
		seen := map[string]bool{}
		for _, iss := range issues {
			key := iss.Source.Addr + "|" + iss.Source.Target
			if seen[key] {
				continue
			}
			seen[key] = true
			fmt.Printf("  beat=%d op=%s addr=%s target=%s reason=%s\n", iss.Beat, iss.Op, iss.Source.Addr, iss.Source.Target, iss.Reason)
		}
	}
}
