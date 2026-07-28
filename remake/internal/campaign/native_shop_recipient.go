package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

// ComposeNativeShopConsumableRecipientFrame reproduces the stable
// 0x2f331→0x2e6b8 target used only when item type >= 0x20. Equipment takes
// the distinct filtered 0x2e8cf→0x2ebe0 comparison panel and must not be
// projected onto this two-column roster.
func ComposeNativeShopConsumableRecipientFrame(
	stable []byte,
	shop *NativeShopAssets,
	rows []NativeRosterRow,
	selected, itemType int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
) ([]byte, error) {
	if shop == nil || itemType < 0x20 {
		return nil, errors.New(
			"campaign: native shop two-column recipient list requires item type >= 0x20",
		)
	}
	return ComposeNativeRosterFrame(
		stable, shop.Panel, rows, selected, strings, font,
	)
}
