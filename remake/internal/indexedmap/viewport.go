package indexedmap

// NativeMapViewport parameterizes the steady tactical view's tile-count
// window. {13,8} reproduces the original EXE's hardcoded 320x200/312x192
// geometry exactly (see the border-math methods below and their proof in
// viewport_test.go); any other size is a remake-only extension used to show
// more of the map on windows/screens bigger than the original 640x400
// presentation, not a recovered EXE constant.
type NativeMapViewport struct {
	Cols, Rows int // visible terrain tile-count window (unit/foreground window is Cols-1, Rows-1 -- see ComposeFrame)
}

const (
	nativeMapTileSize = 24 // fdicon.NativeSize; native sprite/tile pixel size, unchanged by viewport size
	nativeMapBorder   = 4  // fixed border on every edge of the VGA canvas, preserved from 320x200 vs 312x192
)

// DefaultNativeMapViewport is the original, always-supported 13x8 window.
var DefaultNativeMapViewport = NativeMapViewport{Cols: 13, Rows: 8}

// contentWidth/contentHeight are the copied terrain viewport's pixel size
// (312x192 at the original {13,8}) -- the area actually filled with map
// content, excluding the border.
func (v NativeMapViewport) contentWidth() int  { return v.Cols * nativeMapTileSize }
func (v NativeMapViewport) contentHeight() int { return v.Rows * nativeMapTileSize }

// canvasWidth/canvasHeight are the full presented VGA canvas size (320x200
// at the original {13,8}): content plus a fixed border on every edge.
func (v NativeMapViewport) canvasWidth() int  { return v.contentWidth() + 2*nativeMapBorder }
func (v NativeMapViewport) canvasHeight() int { return v.contentHeight() + 2*nativeMapBorder }

// vgaSize is the full indexed VGA buffer's required byte length.
func (v NativeMapViewport) vgaSize() int { return v.canvasWidth() * v.canvasHeight() }

// viewportOffset is the byte offset of the content area's top-left pixel
// within the VGA canvas (0x504 = 4*320+4 at the original {13,8}).
func (v NativeMapViewport) viewportOffset() int {
	return nativeMapBorder*v.canvasWidth() + nativeMapBorder
}

// nativeMapWorkMargin is the fixed off-canvas margin (in pixels) the native
// work buffer keeps on every edge beyond the visible terrain content. It is
// not a derived formula: it reproduces the original EXE's exact recovered
// layout at {13,8} (workBase 0x8088 = 72*456+72, and the paired 0x25680-byte
// unit-present work buffer = 456*336, i.e. a 72px = 3-tile margin on every
// side of the 312x192 content) and is carried forward unchanged as the
// remake's own convention for any wider viewport, since it is exactly the
// slack BlitNativeUnitLayer/BlitNativeForegroundLayer's camera-1/+1 windows
// and NativePlacementOffset's up-to-two-tile pose shifts need on every edge.
const nativeMapWorkMargin = 3 * nativeMapTileSize

// workStride is the native work-buffer row stride required to hold v's
// terrain content plus the fixed margin on both left and right edges. This
// single formula reproduces the original 456 exactly at {13,8} (312+2*72)
// and generalizes it for any wider remake viewport.
func (v NativeMapViewport) workStride() int { return v.contentWidth() + 2*nativeMapWorkMargin }

// workHeight is the native work-buffer row count required to hold v's
// terrain content plus the fixed margin on both top and bottom edges. This
// reproduces the original 336 rows (153216/456) exactly at {13,8}
// (192+2*72).
func (v NativeMapViewport) workHeight() int { return v.contentHeight() + 2*nativeMapWorkMargin }

// workSize is the total native work-buffer byte length required for v. It
// reproduces NativeUnitPresentWorkSize (0x25680 = 456*336) exactly at {13,8}.
func (v NativeMapViewport) workSize() int { return v.workStride() * v.workHeight() }

// workBase is the work-buffer byte offset of the terrain viewport's top-left
// pixel, preserving the original margin on every edge. It reproduces 0x8088
// (72*456+72) exactly at {13,8}.
func (v NativeMapViewport) workBase() int {
	stride := v.workStride()
	return nativeMapWorkMargin*stride + nativeMapWorkMargin
}
