package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

// ComposeNativeShopItemListFrame reproduces 0x2e0bd's completed child-panel
// target: shop resource entry16 at (5,112), followed by 0x2dc55's two-column
// item rows and caller-selected price mode. Opening/closing band timing stays
// outside this stable-frame compositor.
func ComposeNativeShopItemListFrame(
	stable []byte,
	shop *NativeShopAssets,
	itemAssets battle.NativeItemPanelDataAssets,
	itemIDs []int,
	start, selected int,
	effectRows []byte,
	priceMode battle.NativeFacilityPriceMode,
) ([]byte, error) {
	if len(stable) != NativeShopWidth*NativeShopHeight || shop == nil {
		return nil, errors.New("campaign: native shop item-list state is invalid")
	}
	frame := append([]byte(nil), stable...)
	if err := shop.Panel.BlitOpaqueAt(
		frame, NativeShopWidth, 5, 112, false,
	); err != nil {
		return nil, err
	}
	if err := battle.RenderNativeFacilityItemRows(
		itemAssets, shop.PriceCell, itemIDs, start, selected, effectRows,
		priceMode, frame,
	); err != nil {
		return nil, err
	}
	return frame, nil
}
