package fdother

import "fmt"

// BuildNativeIndexedTransitionPass transcribes the raw 0x22046 argument
// mapping. The caller's a1/a2/a3/a4/a5 become the radial center/radius and row
// bounds; notably a2 is both radial CenterY and the final rectangle's exclusive
// EndY in the native routine. Keep this odd alias explicit instead of
// normalizing it into a guessed screen-space rectangle.
func BuildNativeIndexedTransitionPass(centerX, centerY, radius, startY, endY int) (IndexedTransitionPass, error) {
	return BuildNativeIndexedTransitionPassFor(centerX, centerY, radius, startY, endY, NativeTransitionStageWidth, NativeTransitionStageHeight)
}

// BuildNativeIndexedTransitionPassFor is BuildNativeIndexedTransitionPass
// generalized to an explicit stage width/height, for a remake viewport wider
// than the original 13x8 (see indexedmap.NativeMapViewport) whose transition
// stage is no longer the fixed 312x192. ApplyIndexedTransitionPass and
// CopyNativeTransitionViewport already take their geometry entirely from
// caller-supplied fields/params, so this is the only hardcoded piece of the
// transition's own geometry.
func BuildNativeIndexedTransitionPassFor(centerX, centerY, radius, startY, endY, stageWidth, stageHeight int) (IndexedTransitionPass, error) {
	if centerX < 0 || centerX >= stageWidth || centerY < 0 || radius <= 0 || startY < 0 || endY < startY || endY > stageHeight {
		return IndexedTransitionPass{}, fmt.Errorf("indexed transition: invalid raw 0x22046 args")
	}
	return IndexedTransitionPass{
		FirstRadial: RadialLUTRemap{
			CenterX: centerX, CenterY: centerY, Radius: radius, Scale: 16,
			StartY: startY, EndY: endY, ClipWidth: stageWidth,
		},
		SecondRadial: RadialLUTRemap{
			CenterX: centerX, CenterY: centerY, Radius: radius, Scale: 16,
			StartY: centerY, EndY: endY, ClipWidth: stageWidth,
		},
		FinalRect: CenteredRectLUTRemap{
			CenterX: centerX, HorizontalRadius: radius * 16 / 10,
			StartY: startY, EndY: centerY, ClipWidth: stageWidth,
		},
	}, nil
}
