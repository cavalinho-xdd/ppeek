import QtQuick
import QtQuick.Window

// Frameless always-on-top host for the HUD where layer-shell is missing
// (Windows, X11). Click-through via WindowTransparentForInput (real
// WS_EX_TRANSPARENT on Windows). overlay/main.py positions the window on
// screen from the anchor + margin settings.
Window {
    width: hud.width
    height: hud.height
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
         | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput

    Hud {
        id: hud
        // stays mapped; hidden through opacity like the layer-shell host
        opacity: hub.visible ? 1 : 0
        visible: opacity > 0
    }
}
