package campaign

import (
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

const (
	NativeClassListStride = 320
	NativeClassListHeight = 200
	NativeClassListRows   = 3
	nativeClassPanelX     = 5
	nativeClassPanelY     = 112
	nativeClassPanelW     = 310
	nativeClassPanelH     = 86
)

// NativeClassListRow is one already-resolved row consumed by 0x31019.
// Sprite is the party FDICON pointer selected by the native roster slot and
// global cycle; resolving that pointer remains the caller's responsibility.
type NativeClassListRow struct {
	Sprite             fdicon.Sprite
	NameTextIndex      int
	CurrentClassTextID int
	TargetClassTextID  int
}

// RenderNativeClassListRows reproduces the proven row subpass of 0x31019.
// It deliberately does not invent the surrounding 0x1974c opening frame.
// The destination is updated atomically only after all sprites and strings
// validate.
func RenderNativeClassListRows(
	dst []byte,
	rows []NativeClassListRow,
	selected int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
) error {
	if len(dst) != NativeClassListStride*NativeClassListHeight {
		return errors.New("campaign: native class list requires a 320x200 indexed frame")
	}
	if len(rows) == 0 || len(rows) > NativeClassListRows || selected < 0 || selected >= len(rows) {
		return errors.New("campaign: invalid native class list rows or selection")
	}
	if strings == nil || font == nil {
		return errors.New("campaign: native class list text assets are unavailable")
	}
	staged := append([]byte(nil), dst...)
	for i, row := range rows {
		if err := row.Sprite.BlitAt(staged, NativeClassListStride, 14, 117+26*i); err != nil {
			return fmt.Errorf("campaign: native class row %d sprite: %w", i, err)
		}
		foreground := byte(205)
		if i == selected {
			foreground = 201
		}
		y := 121 + 26*i
		texts := []struct {
			x     int
			index int
		}{
			{40, row.NameTextIndex},
			{130, row.CurrentClassTextID + 150},
			{175, 593},
			{239, row.TargetClassTextID + 150},
		}
		for _, text := range texts {
			if err := blitNativeClassListText(staged, strings, font, text.x, y, text.index, foreground); err != nil {
				return fmt.Errorf("campaign: native class row %d text %d: %w", i, text.index, err)
			}
		}
	}
	copy(dst, staged)
	return nil
}

// ComposeNativeClassListFrame first applies FDOTHER #14 LMI1 entry #16 using
// 0x4e8af's opaque path, then runs the 0x31019 row subpass.
func ComposeNativeClassListFrame(
	background []byte,
	panel fdother.LMI1Entry,
	rows []NativeClassListRow,
	selected int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
) ([]byte, error) {
	if len(background) != NativeClassListStride*NativeClassListHeight {
		return nil, errors.New("campaign: native class background requires a 320x200 indexed frame")
	}
	if panel.Width != nativeClassPanelW || panel.Height != nativeClassPanelH {
		return nil, fmt.Errorf("campaign: native class panel is %dx%d, want 310x86", panel.Width, panel.Height)
	}
	frame := append([]byte(nil), background...)
	if err := panel.BlitOpaqueAt(frame, NativeClassListStride, nativeClassPanelX, nativeClassPanelY, false); err != nil {
		return nil, fmt.Errorf("campaign: native class panel: %w", err)
	}
	if err := RenderNativeClassListRows(frame, rows, selected, strings, font); err != nil {
		return nil, err
	}
	return frame, nil
}

// NativeClassListOpeningFrames reproduces 0x311DC's six calls to 0x1974c.
// Each pass starts from the untouched snapshot and copies an increasingly
// complete 310-pixel-wide slice from composed y=112 to destination y.
func NativeClassListOpeningFrames(background, composed []byte) ([][]byte, error) {
	if len(background) != NativeClassListStride*NativeClassListHeight ||
		len(composed) != NativeClassListStride*NativeClassListHeight {
		return nil, errors.New("campaign: native class opening requires two 320x200 indexed frames")
	}
	out := make([][]byte, 0, 6)
	for i := 5; i >= 0; i-- {
		destinationY := 13*i + nativeClassPanelY
		height := nativeClassPanelH
		if destinationY+height > NativeClassListHeight {
			height = NativeClassListHeight - destinationY
		}
		frame := append([]byte(nil), background...)
		for row := 0; row < height; row++ {
			src := (nativeClassPanelY+row)*NativeClassListStride + nativeClassPanelX
			dst := (destinationY+row)*NativeClassListStride + nativeClassPanelX
			copy(frame[dst:dst+nativeClassPanelW], composed[src:src+nativeClassPanelW])
		}
		out = append(out, frame)
	}
	return out, nil
}

// NativeClassListClosingFrames reproduces 0x2d31b's five 0x1974c passes
// (i=1..5). The caller must present the untouched source restore afterward.
func NativeClassListClosingFrames(background, composed []byte) ([][]byte, error) {
	if len(background) != NativeClassListStride*NativeClassListHeight ||
		len(composed) != NativeClassListStride*NativeClassListHeight {
		return nil, errors.New("campaign: native class closing requires two 320x200 indexed frames")
	}
	out := make([][]byte, 0, 5)
	for i := 1; i < 6; i++ {
		destinationY := 13*i + nativeClassPanelY
		height := nativeClassPanelH
		if destinationY+height > NativeClassListHeight {
			height = NativeClassListHeight - destinationY
		}
		frame := append([]byte(nil), background...)
		for row := 0; row < height; row++ {
			src := (nativeClassPanelY+row)*NativeClassListStride + nativeClassPanelX
			dst := (destinationY+row)*NativeClassListStride + nativeClassPanelX
			copy(frame[dst:dst+nativeClassPanelW], composed[src:src+nativeClassPanelW])
		}
		out = append(out, frame)
	}
	return out, nil
}

func blitNativeClassListText(
	dst []byte,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	x, y, index int,
	foreground byte,
) error {
	words, err := strings.Words(index)
	if err != nil {
		return err
	}
	style := fdtxt.NativeGlyphStyle{Foreground: foreground, Shadow: 76}
	for i, word := range words {
		if word >= fdtxt.ControlMin {
			return fmt.Errorf("text contains native control %#x", word)
		}
		offset := y*NativeClassListStride + x + i*fdtxt.GlyphWidth
		if err := font.BlitNativeGlyph(dst, NativeClassListStride, offset, int(word), style); err != nil {
			return err
		}
	}
	return nil
}
