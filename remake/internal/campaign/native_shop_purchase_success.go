package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
)

type NativeShopPurchaseSuccessPlan struct {
	HubVariant             int
	ResourceID             int
	FrameCount             int
	EffectOffset           int
	PreDelayBIOSTicks      int
	PerFrameDelayBIOSTicks int
	PostDelayBIOSTicks     int
	RestorePortraitMode0   bool
	OptionalEquipBefore    bool
	DebitAfterPresentation bool
	ReturnToProductLoop    bool
}

// PlanNativeShopPurchaseSuccess preserves the three shop cases in 0x2f4c6.
// Church case 4 is intentionally owned by PlanNativeChurchReviveSuccess.
func PlanNativeShopPurchaseSuccess(
	hubVariant int,
) (NativeShopPurchaseSuccessPlan, error) {
	switch hubVariant {
	case 1:
		return NativeShopPurchaseSuccessPlan{
			HubVariant: 1, ResourceID: 12, FrameCount: 5,
			EffectOffset:           45*NativeShopWidth + 169,
			PerFrameDelayBIOSTicks: 2, RestorePortraitMode0: true,
			OptionalEquipBefore: true, DebitAfterPresentation: true,
			ReturnToProductLoop: true,
		}, nil
	case 3:
		return NativeShopPurchaseSuccessPlan{
			HubVariant: 3, ResourceID: 29, FrameCount: 1,
			EffectOffset:      39*NativeShopWidth + 148,
			PreDelayBIOSTicks: 1, PostDelayBIOSTicks: 8,
			RestorePortraitMode0: true,
			OptionalEquipBefore:  true, DebitAfterPresentation: true,
			ReturnToProductLoop: true,
		}, nil
	case 5:
		return NativeShopPurchaseSuccessPlan{
			HubVariant: 5, ResourceID: 63, FrameCount: 7,
			EffectOffset:           28*NativeShopWidth + 131,
			PerFrameDelayBIOSTicks: 2,
			OptionalEquipBefore:    true, DebitAfterPresentation: true,
			ReturnToProductLoop: true,
		}, nil
	default:
		return NativeShopPurchaseSuccessPlan{}, errors.New(
			"campaign: unsupported native shop success variant",
		)
	}
}

// ComposeNativeShopPurchaseSuccessFrames applies resource entries 23 onward
// cumulatively through 0x16886. For variants 1/3, 0x16559(0) then restores
// the current facility portrait; variant 5 has no portrait restore call.
func ComposeNativeShopPurchaseSuccessFrames(
	background []byte,
	shop *NativeShopAssets,
	portrait dato.Frame,
	portraitID, hubVariant int,
) (animation [][]byte, final []byte, err error) {
	plan, err := PlanNativeShopPurchaseSuccess(hubVariant)
	if err != nil {
		return nil, nil, err
	}
	if len(background) != NativeShopWidth*NativeShopHeight || shop == nil ||
		shop.ResourceID != plan.ResourceID ||
		len(shop.SuccessFrames) != plan.FrameCount {
		return nil, nil, errors.New(
			"campaign: native shop success assets do not match the hub variant",
		)
	}
	staged := append([]byte(nil), background...)
	animation = make([][]byte, 0, len(shop.SuccessFrames))
	for _, effect := range shop.SuccessFrames {
		if err := effect.BlitAt(
			staged, NativeShopWidth, plan.EffectOffset, -1,
		); err != nil {
			return nil, nil, err
		}
		animation = append(animation, append([]byte(nil), staged...))
	}
	final = append([]byte(nil), staged...)
	if plan.RestorePortraitMode0 {
		if err := portrait.BlitAtOffset(
			final, NativeShopWidth, nativeFacilityPortraitOffset(portraitID),
		); err != nil {
			return nil, nil, err
		}
	}
	return animation, final, nil
}
