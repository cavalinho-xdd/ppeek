import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

// Skin-driven themes (see overlay/theme.py + bridge.py):
//  - night:  Fool Moon Night — deep black, white hand-drawn outlines, Gaegu font
//  - pastel: Arona & Plana (Blue Archive) — pastel blue on navy, Readex Pro,
//            red halo + string, diagonal stripe clusters, diamonds and sparks
Window {
    id: root
    readonly property int hudWidth: 252
    readonly property int hudHeight: 118
    width: hudWidth + hub.marginX
    height: hudHeight + hub.marginY
    visible: hub.visible
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput

    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: hub.anchorFlags
    LayerShell.Window.exclusionZone: 0
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.scope: "osusayohub-overlay"

    readonly property bool pastel: hub.scene === "pastel"
    readonly property string ink: hub.ink
    readonly property string inkDim: hub.inkDim
    readonly property string paper: hub.paper
    readonly property string accent: hub.accent
    readonly property string decoRed: hub.decoRed
    readonly property string blood: hub.missColor
    // bundled Readex Pro wins; falls back to a system-installed copy (or Sans)
    readonly property string fontFamily: pastel
        ? (readex.status === FontLoader.Ready ? readex.name : hub.themeFont)
        : gaegu.name

    // pastel grade inks — cartoonish but muted, so they sit in the b/w night scene
    readonly property var gradeColors: ({
        "SS": "#e9d18b",   // soft gold
        "S":  "#9fc6ea",   // pastel blue
        "A":  "#a9d9a2",   // pastel green
        "B":  "#eab98c",   // pastel orange
        "C":  "#e29a9a",   // washed rose
        "D":  "#c84040"    // blood red
    })

    Item {
        // margins emulated as transparent padding (see bridge.py note)
        width: root.hudWidth
        height: root.hudHeight
        x: hub.anchoredLeft ? hub.marginX : (hub.anchoredRight ? 0 : hub.marginX / 2)
        y: hub.anchoredTop ? hub.marginY : 0

        // offset second outline — sketchy double-line look
        Rectangle {
            anchors.fill: parent
            anchors.leftMargin: 3
            anchors.topMargin: 3
            anchors.rightMargin: -3
            anchors.bottomMargin: -3
            color: "transparent"
            border.color: root.inkDim
            border.width: 1
            radius: 2
            rotation: 0.4
            opacity: 0.55
        }

        Rectangle {
            id: panel
            anchors.fill: parent
            color: root.paper
            border.color: root.ink
            border.width: 2
            radius: 2

            // -- FULL MOON NIGHT scenery (behind the numbers) ------------

            // twinkling star field
            Repeater {
                model: 18
                Rectangle {
                    readonly property real s: 0.5 + Math.random() * 1.1
                    x: 8 + Math.random() * (panel.width - 16)
                    y: 6 + Math.random() * (panel.height - 24)
                    width: s * 2; height: s * 2; radius: s
                    color: root.ink
                    opacity: 0.15
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        PauseAnimation { duration: Math.random() * 2200 }
                        NumberAnimation { to: 0.85; duration: 500 + Math.random() * 900; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.12; duration: 500 + Math.random() * 900; easing.type: Easing.InOutSine }
                    }
                }
            }

            // four-point sparkle stars, like the hand-drawn sky
            Repeater {
                model: 3
                Item {
                    x: 20 + Math.random() * (panel.width - 40)
                    y: 10 + Math.random() * (panel.height * 0.45)
                    opacity: 0.25
                    Rectangle { x: -4; y: -0.5; width: 8; height: 1; color: root.ink }
                    Rectangle { x: -0.5; y: -4; width: 1; height: 8; color: root.ink }
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        PauseAnimation { duration: Math.random() * 3000 }
                        NumberAnimation { to: 0.8; duration: 700 + Math.random() * 700; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.2; duration: 700 + Math.random() * 700; easing.type: Easing.InOutSine }
                    }
                }
            }

            // hatched planets + crescent moon, drawn once (night scene only)
            Canvas {
                anchors.fill: parent
                visible: !root.pastel
                Component.onCompleted: requestPaint()
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    function ringHalf(cx, cy, r, alpha, a0, a1) {
                        ctx.save()
                        ctx.translate(cx, cy)
                        ctx.rotate(-18 * Math.PI / 180)
                        ctx.scale(1, 0.32)
                        ctx.strokeStyle = "rgba(242,242,242," + alpha * 0.9 + ")"
                        ctx.lineWidth = 1.2
                        var ks = [1.55, 1.75, 1.95]
                        for (var j = 0; j < ks.length; j++) {
                            ctx.beginPath()
                            ctx.arc(0, 0, r * ks[j], a0, a1)
                            ctx.stroke()
                        }
                        ctx.restore()
                    }

                    function planet(cx, cy, r, alpha, ringed) {
                        if (ringed)  // far half of the ring, behind the body
                            ringHalf(cx, cy, r, alpha, Math.PI, 2 * Math.PI)
                        ctx.save()
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                        ctx.clip()
                        ctx.fillStyle = "rgba(6,6,6,0.92)"
                        ctx.fill()
                        ctx.strokeStyle = "rgba(242,242,242," + alpha * 0.5 + ")"
                        ctx.lineWidth = 1
                        var i = 0  // wavy horizontal hatching, clipped to the disc
                        for (var y = -r + 3; y < r; y += 3.2, i++) {
                            var bow = 0.15 * r * Math.sin(i * 1.7)
                            ctx.beginPath()
                            ctx.moveTo(cx - r, cy + y + bow)
                            ctx.quadraticCurveTo(cx, cy + y + bow + 2.5, cx + r, cy + y + bow)
                            ctx.stroke()
                        }
                        ctx.restore()
                        ctx.strokeStyle = "rgba(242,242,242," + alpha + ")"
                        ctx.lineWidth = 1.3
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                        ctx.stroke()
                        if (ringed)  // near half, in front of the body
                            ringHalf(cx, cy, r, alpha, 0, Math.PI)
                    }

                    function moon(cx, cy, r, alpha) {
                        ctx.save()
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                        ctx.fillStyle = "rgba(242,242,242," + alpha * 0.85 + ")"
                        ctx.fill()
                        ctx.globalCompositeOperation = "destination-out"
                        ctx.beginPath()
                        ctx.arc(cx + r * 0.45, cy - r * 0.25, r * 0.85, 0, 2 * Math.PI)
                        ctx.fill()
                        ctx.globalCompositeOperation = "source-over"
                        ctx.strokeStyle = "rgba(242,242,242," + alpha + ")"
                        ctx.lineWidth = 1
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                        ctx.stroke()
                        ctx.restore()
                    }

                    planet(width - 34, 20, 13, 0.5, true)   // ringed, behind grade
                    planet(width * 0.40, 13, 5, 0.4, false)
                    moon(width * 0.55, 15, 6, 0.7)
                }
            }

            // water ripples along the bottom edge, drifting outward (night only)
            Canvas {
                id: ripples
                anchors.bottom: parent.bottom
                width: parent.width
                height: 26
                visible: !root.pastel
                opacity: 0.45
                property real phase: 0
                NumberAnimation on phase { from: 0; to: 1; duration: 2200; loops: Animation.Infinite }
                onPhaseChanged: requestPaint()
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var cx = width / 2, cy = height - 2
                    var gap = 14, maxr = width * 0.55
                    for (var r0 = 8 + phase * gap; r0 < maxr; r0 += gap) {
                        var fade = 1 - r0 / maxr
                        ctx.strokeStyle = "rgba(242,242,242," + 0.5 * fade + ")"
                        ctx.lineWidth = 1
                        ctx.save()
                        ctx.translate(cx, cy)
                        ctx.scale(1, 0.18)
                        ctx.beginPath()
                        ctx.arc(0, 0, r0, Math.PI, 2 * Math.PI)
                        ctx.stroke()
                        ctx.restore()
                    }
                }
            }

            // -- ARONA & PLANA pastel scenery (Blue Archive motifs) -------

            // stripe clusters, dot grids, red halo + trailing string + heart
            Canvas {
                id: pastelScene
                anchors.fill: parent
                visible: root.pastel
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
                Connections { target: hub; function onThemeChanged() { pastelScene.requestPaint() } }
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    function stripes(cx, cy, angle) {
                        // diagonal stack of rounded bars, like the skin corners
                        ctx.save()
                        ctx.translate(cx, cy)
                        ctx.rotate(angle * Math.PI / 180)
                        var bars = [
                            [0, -8, 20, 4, root.ink, 0.24],
                            [5, -1, 32, 5, root.accent, 0.36],
                            [-6, 6, 24, 4, root.ink, 0.5],
                            [8, 12, 16, 3, root.accent, 0.22],
                        ]
                        for (var i = 0; i < bars.length; i++) {
                            var b = bars[i]
                            ctx.fillStyle = b[4]
                            ctx.globalAlpha = b[5]
                            ctx.beginPath()
                            ctx.roundedRect(b[0] - b[2] / 2, b[1], b[2], b[3], b[3] / 2, b[3] / 2)
                            ctx.fill()
                        }
                        ctx.restore()
                        ctx.globalAlpha = 1
                    }

                    function dotGrid(x0, y0) {
                        ctx.fillStyle = root.ink
                        ctx.globalAlpha = 0.4
                        for (var gy = 0; gy < 3; gy++)
                            for (var gx = 0; gx < 6; gx++) {
                                ctx.beginPath()
                                ctx.arc(x0 + gx * 4.5, y0 + gy * 4.5, 0.8, 0, 2 * Math.PI)
                                ctx.fill()
                            }
                        ctx.globalAlpha = 1
                    }

                    stripes(width - 12, 10, -45)
                    stripes(12, height - 26, 135)
                    dotGrid(10, 10)
                    dotGrid(width - 60, height - 18)

                    // red string trailing from the halo, with a tiny heart
                    ctx.strokeStyle = root.decoRed
                    ctx.globalAlpha = 0.35
                    ctx.lineWidth = 1
                    ctx.beginPath()
                    ctx.moveTo(width * 0.56 - 12, 14)
                    ctx.bezierCurveTo(width * 0.40, height * 0.50,
                                      width * 0.16, height * 0.42,
                                      -4, height * 0.86)
                    ctx.stroke()

                    var hx = width * 0.15, hy = height * 0.52
                    ctx.fillStyle = root.decoRed
                    ctx.globalAlpha = 0.6
                    ctx.beginPath()
                    ctx.moveTo(hx, hy + 2.4)
                    ctx.bezierCurveTo(hx - 3.2, hy - 0.6, hx - 1.7, hy - 2.8, hx, hy - 0.9)
                    ctx.bezierCurveTo(hx + 1.7, hy - 2.8, hx + 3.2, hy - 0.6, hx, hy + 2.4)
                    ctx.fill()

                    // Arona's red halo, tilted, where the moon hangs at night
                    ctx.save()
                    ctx.translate(width * 0.56, 13)
                    ctx.rotate(-14 * Math.PI / 180)
                    ctx.scale(1, 0.35)
                    ctx.strokeStyle = root.decoRed
                    ctx.globalAlpha = 0.85
                    ctx.lineWidth = 2
                    ctx.beginPath()
                    ctx.arc(0, 0, 13, 0, 2 * Math.PI)
                    ctx.stroke()
                    ctx.globalAlpha = 0.3
                    ctx.lineWidth = 1
                    ctx.beginPath()
                    ctx.arc(0, 0, 17, 0, 2 * Math.PI)
                    ctx.stroke()
                    ctx.restore()
                    ctx.globalAlpha = 1
                }
            }

            // drifting pastel diamonds — sparse red ones pop like the string
            Repeater {
                model: 7
                Rectangle {
                    readonly property real s: 2.2 + Math.random() * 2.4
                    visible: root.pastel
                    x: 10 + Math.random() * (panel.width - 20)
                    y: 8 + Math.random() * (panel.height - 30)
                    width: s; height: s
                    rotation: 45
                    color: index % 4 === 3 ? root.decoRed : root.ink
                    opacity: 0.2
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        PauseAnimation { duration: Math.random() * 2600 }
                        NumberAnimation { to: 0.7; duration: 600 + Math.random() * 800; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.15; duration: 600 + Math.random() * 800; easing.type: Easing.InOutSine }
                    }
                }
            }

            // slowly rotating hollow squares in the accent blue
            Repeater {
                model: 4
                Rectangle {
                    readonly property real s: 6 + Math.random() * 6
                    visible: root.pastel
                    x: 14 + Math.random() * (panel.width - 34)
                    y: 8 + Math.random() * (panel.height - 34)
                    width: s; height: s
                    color: "transparent"
                    border.color: root.accent
                    border.width: 1
                    opacity: 0.4
                    RotationAnimation on rotation {
                        from: Math.random() * 90; to: 360
                        duration: 14000 + Math.random() * 8000
                        loops: Animation.Infinite
                    }
                }
            }

            // sketchbook corner brackets, like the album-cover frame
            Repeater {
                model: [
                    { cx: 5,  cy: 5,  dx: 1,  dy: 1 },
                    { cx: panel.width - 5, cy: 5, dx: -1, dy: 1 },
                    { cx: 5,  cy: panel.height - 5, dx: 1, dy: -1 },
                    { cx: panel.width - 5, cy: panel.height - 5, dx: -1, dy: -1 }
                ]
                Item {
                    x: modelData.cx; y: modelData.cy
                    opacity: 0.55
                    Rectangle { x: modelData.dx > 0 ? 0 : -9; y: 0; width: 9; height: 1; color: root.ink }
                    Rectangle { x: 0; y: modelData.dy > 0 ? 0 : -9; width: 1; height: 9; color: root.ink }
                }
            }

            // -- live numbers --------------------------------------------

            // PP hero
            Text {
                id: ppText
                x: 14; y: 2
                color: root.ink
                font.family: root.fontFamily
                font.pixelSize: 32
                font.bold: true
                property real shownPp: 0
                Behavior on shownPp { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Connections { target: hub; function onFrameChanged() { ppText.shownPp = hub.pp } }
                text: Math.round(shownPp) + (root.pastel ? "pp" : " p p")
            }

            // grade — pastel ink per rank (SS gold … D blood red)
            Text {
                id: gradeText
                anchors.right: parent.right; anchors.rightMargin: 14
                y: 4
                color: root.gradeColors[hub.grade] || root.ink
                font.family: root.fontFamily
                font.pixelSize: 30
                font.bold: true
                text: hub.grade
                Behavior on color { ColorAnimation { duration: 350 } }
                // little pop when the rank changes
                onTextChanged: gradePop.restart()
                SequentialAnimation {
                    id: gradePop
                    NumberAnimation { target: gradeText; property: "scale"; to: 1.3; duration: 70 }
                    NumberAnimation { target: gradeText; property: "scale"; to: 1.0; duration: 200; easing.type: Easing.OutBack }
                }
            }

            Row {
                x: 14; y: 40
                spacing: 12
                Text {
                    id: comboText
                    color: root.inkDim
                    font.family: root.fontFamily
                    font.pixelSize: 15
                    text: hub.combo + "x"
                    property int last: 0
                    Connections {
                        target: hub
                        function onFrameChanged() {
                            if (hub.combo > comboText.last)
                                comboPop.restart()
                            comboText.last = hub.combo
                        }
                    }
                    SequentialAnimation {
                        id: comboPop
                        NumberAnimation { target: comboText; property: "scale"; to: 1.25; duration: 60 }
                        NumberAnimation { target: comboText; property: "scale"; to: 1.0; duration: 160; easing.type: Easing.OutCubic }
                    }
                }
                Text { color: root.inkDim; font.family: root.fontFamily; font.pixelSize: 15; text: hub.accuracy.toFixed(2) + "%" }
                Text { color: root.inkDim; font.family: root.fontFamily; font.pixelSize: 15; text: hub.kps.toFixed(0) + "kps" }
            }

            // hit counts, dot-separated, white with red misses
            Row {
                x: 14; y: 62
                spacing: 7
                Text { color: root.ink;    font.family: root.fontFamily; font.pixelSize: 13; text: hub.hits300 }
                Text { color: root.inkDim; font.family: root.fontFamily; font.pixelSize: 13; text: "·" }
                Text { color: root.ink;    font.family: root.fontFamily; font.pixelSize: 13; text: hub.hits100 }
                Text { color: root.inkDim; font.family: root.fontFamily; font.pixelSize: 13; text: "·" }
                Text { color: root.ink;    font.family: root.fontFamily; font.pixelSize: 13; text: hub.hits50 }
                Text { color: root.inkDim; font.family: root.fontFamily; font.pixelSize: 13; text: "·" }
                Text { color: root.blood;  font.family: root.fontFamily; font.pixelSize: 13; text: hub.hitsMiss }
            }

            Text {
                anchors.right: parent.right; anchors.rightMargin: 14
                y: 62
                color: root.inkDim
                font.family: root.fontFamily
                font.pixelSize: 13
                font.letterSpacing: 2
                text: "UR " + hub.ur.toFixed(1)
            }

            // hit-error meter — monochrome bands
            Item {
                id: meter
                x: 14; y: 86
                width: parent.width - 28
                height: 20

                Repeater {
                    model: [
                        { w: 97.0, o: 0.14 },
                        { w: 64.0, o: 0.26 },
                        { w: 16.0, o: 0.48 }
                    ]
                    Rectangle {
                        property real half: (modelData.w / 110.0) * meter.width / 2
                        x: meter.width / 2 - half
                        y: meter.height / 2 - 2
                        width: half * 2
                        height: 4
                        color: root.ink
                        opacity: modelData.o
                    }
                }

                Rectangle {  // center line
                    x: meter.width / 2 - 1
                    width: 2; height: meter.height
                    color: root.ink
                }

                Repeater {  // recent hits; misses beyond 50-window bleed red
                    model: hub.errorTicks
                    Rectangle {
                        x: meter.width / 2 + modelData.pos * meter.width / 2 - 1
                        y: 3
                        width: 2
                        height: meter.height - 6
                        color: Math.abs(modelData.pos) > 0.88 ? root.blood : root.ink
                        opacity: 0.9 * (1.0 - modelData.age)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: !hub.connected
                color: root.inkDim
                font.family: root.fontFamily
                font.pixelSize: 15
                font.letterSpacing: 3
                horizontalAlignment: Text.AlignHCenter
                text: "w a i t i n g   f o r   o s u !\n( t o s u )"
            }
        }
    }

    FontLoader {
        id: gaegu
        source: hub.fontPath
    }
    FontLoader {
        id: readex
        source: hub.pastelFontPath
    }
    FontLoader {
        source: hub.pastelFontBoldPath  // registers the bold face for font.bold
    }
}
