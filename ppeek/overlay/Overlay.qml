import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

// wlr-layer-shell host for the HUD (Wayland with layer-shell-qt): sits on
// the overlay layer, so it shows above fullscreen games.
Window {
    id: root
    width: hud.width + hub.marginX
    height: hud.height + hub.marginY
    // Qt LayerShellQt only completes the wlr-layer-shell configure/commit
    // handshake on the window's first show(); toggling `visible` later
    // (e.g. entering gameplay after starting hidden) leaves the surface
    // unmapped on wlroots compositors. Stay mapped always and drive the
    // actual show/hide through the content's opacity instead.
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput

    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: hub.anchorFlags
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.scope: "osusayohub-overlay"

    Hud {
        id: hud
        // margins emulated as transparent padding (see bridge.py note)
        x: hub.anchoredLeft ? hub.marginX : (hub.anchoredRight ? 0 : hub.marginX / 2)
        y: hub.anchoredTop ? hub.marginY : 0
        opacity: hub.visible ? 1 : 0
        visible: opacity > 0
    }
}
