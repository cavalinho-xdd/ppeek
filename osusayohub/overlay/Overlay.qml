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
    readonly property bool night: hub.scene === "night"
    readonly property bool freedom: hub.scene === "freedom"
    readonly property bool clearblack: hub.scene === "clearblack"
    readonly property string ink: hub.ink
    readonly property string inkDim: hub.inkDim
    readonly property string paper: hub.paper
    readonly property string accent: hub.accent
    readonly property string decoRed: hub.decoRed
    readonly property string blood: hub.missColor
    // bundled fonts win; falls back to a system-installed copy (or Sans).
    // clearBlack ships no custom font at all, so it just takes hub.themeFont.
    readonly property string fontFamily: {
        if (freedom) return (freedomFont.status === FontLoader.Ready ? freedomFont.name : hub.themeFont)
        if (pastel) return (quicksand.status === FontLoader.Ready ? quicksand.name : hub.themeFont)
        if (clearblack) return hub.themeFont
        return (gaegu.status === FontLoader.Ready ? gaegu.name : hub.themeFont)
    }

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
                visible: root.night
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
                visible: root.night
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

            // -- FREEDOM DIVE REIMAGINED cosmic scenery -------------------

            Canvas {
                id: freedomScene
                anchors.fill: parent
                visible: root.freedom
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
                property real t: 0
                NumberAnimation on t { from: 0; to: Math.PI * 2; duration: 4000; loops: Animation.Infinite; running: freedomScene.visible }
                onTChanged: requestPaint()
                Connections { target: hub; function onThemeChanged() { freedomScene.requestPaint() } }

                // stable random seeds
                property var confetti: []
                property var sparkles: []
                property bool seeded: false
                function ensureSeeds() {
                    if (seeded) return
                    seeded = true
                    // pseudo-random from a fixed seed
                    function sr(s) { s = (s * 9301 + 49297) % 233280; return s / 233280.0 }
                    var s = 1222
                    confetti = []
                    for (var i = 0; i < 14; i++) {
                        s = (s * 9301 + 49297) % 233280; var fx = s / 233280.0
                        s = (s * 9301 + 49297) % 233280; var fy = s / 233280.0
                        s = (s * 9301 + 49297) % 233280; var sz = 1.5 + (s / 233280.0) * 2.0
                        s = (s * 9301 + 49297) % 233280; var ph = (s / 233280.0) * 6.28
                        s = (s * 9301 + 49297) % 233280; var sp = 0.6 + (s / 233280.0) * 1.2
                        s = (s * 9301 + 49297) % 233280; var rt = (s / 233280.0) * 360
                        confetti.push({fx: fx, fy: fy, sz: sz, ph: ph, sp: sp, rt: rt})
                    }
                    sparkles = []
                    for (var j = 0; j < 6; j++) {
                        s = (s * 9301 + 49297) % 233280; var sfx = s / 233280.0
                        s = (s * 9301 + 49297) % 233280; var sfy = s / 233280.0
                        s = (s * 9301 + 49297) % 233280; var ssz = 2.0 + (s / 233280.0) * 2.5
                        s = (s * 9301 + 49297) % 233280; var sph = (s / 233280.0) * 6.28
                        s = (s * 9301 + 49297) % 233280; var ssp = 0.5 + (s / 233280.0) * 1.1
                        sparkles.push({fx: sfx, fy: sfy, sz: ssz, ph: sph, sp: ssp})
                    }
                }

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ensureSeeds()

                    // shooting star arrows from corners
                    function shootingArrow(x0, y0, x1, y1, thickness, seed) {
                        var pulse = 0.15 + 0.12 * Math.sin(t * 1.3 + seed * 2.5)
                        var grad = ctx.createLinearGradient(x0, y0, x1, y1)
                        grad.addColorStop(0.0, "rgba(255,80,60," + pulse + ")")
                        grad.addColorStop(0.25, "rgba(255,200,50," + pulse + ")")
                        grad.addColorStop(0.5, "rgba(100,230,100," + pulse + ")")
                        grad.addColorStop(0.75, "rgba(80,180,255," + pulse + ")")
                        grad.addColorStop(1.0, "rgba(180,100,255," + pulse + ")")
                        ctx.strokeStyle = grad
                        ctx.lineWidth = thickness
                        ctx.lineCap = "round"
                        ctx.beginPath()
                        ctx.moveTo(x0, y0)
                        ctx.lineTo(x1, y1)
                        ctx.stroke()
                    }
                    shootingArrow(-8, height + 4, width * 0.45, height * 0.35, 14, 0)
                    shootingArrow(width + 8, -4, width * 0.55, height * 0.7, 10, 1)

                    // white diamond confetti
                    for (var ci = 0; ci < confetti.length; ci++) {
                        var c = confetti[ci]
                        var tw = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(t * c.sp + c.ph))
                        var cx2 = c.fx * width, cy2 = c.fy * height
                        ctx.save()
                        ctx.translate(cx2, cy2)
                        ctx.rotate((c.rt + t * c.sp * 15) * Math.PI / 180)
                        ctx.fillStyle = "rgba(255,255,255," + (0.63 * tw) + ")"
                        var ss = c.sz * 0.7
                        ctx.fillRect(-ss / 2, -ss / 2, ss, ss)
                        ctx.restore()
                    }

                    // golden sparkle stars
                    for (var si = 0; si < sparkles.length; si++) {
                        var sk = sparkles[si]
                        var stw = 0.2 + 0.8 * (0.5 + 0.5 * Math.sin(t * sk.sp + sk.ph))
                        var sx = sk.fx * width, sy = sk.fy * height
                        var gs = sk.sz * (0.8 + 1.2 * stw)
                        ctx.strokeStyle = "rgba(255,220,80," + (0.86 * stw) + ")"
                        ctx.lineWidth = 1.5
                        ctx.beginPath(); ctx.moveTo(sx - gs, sy); ctx.lineTo(sx + gs, sy); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(sx, sy - gs); ctx.lineTo(sx, sy + gs); ctx.stroke()
                        var ds = gs * 0.5
                        ctx.strokeStyle = "rgba(255,220,80," + (0.5 * stw) + ")"
                        ctx.lineWidth = 1.0
                        ctx.beginPath(); ctx.moveTo(sx - ds, sy - ds); ctx.lineTo(sx + ds, sy + ds); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(sx - ds, sy + ds); ctx.lineTo(sx + ds, sy - ds); ctx.stroke()
                    }

                    // three blob planets
                    function blobPlanet(cx, cy, r, seed) {
                        ctx.save()
                        ctx.translate(cx, cy)
                        var pulse = Math.sin(t * 1.5 + seed) * 0.06
                        var wobble = Math.sin(t * 0.8 + seed * 1.7) * 0.07
                        ctx.rotate(wobble)
                        ctx.scale(1 + pulse, 1 - pulse)

                        // rainbow ring gradient
                        var grad = ctx.createLinearGradient(-r * 2.2, 0, r * 2.2, 0)
                        grad.addColorStop(0.0, "rgb(255,100,60)")
                        grad.addColorStop(0.2, "rgb(255,200,50)")
                        grad.addColorStop(0.4, "rgb(100,230,100)")
                        grad.addColorStop(0.6, "rgb(80,220,255)")
                        grad.addColorStop(0.8, "rgb(100,120,255)")
                        grad.addColorStop(1.0, "rgb(200,100,255)")

                        var ringAng = (15 + t * 25 * (seed % 2 === 0 ? 1 : -1)) * Math.PI / 180

                        // ring back half
                        ctx.save()
                        ctx.rotate(ringAng)
                        ctx.scale(1, 0.26)
                        ctx.strokeStyle = grad
                        ctx.lineWidth = r * 0.3
                        ctx.beginPath()
                        ctx.arc(0, 0, r * 1.9, Math.PI, 2 * Math.PI)
                        ctx.stroke()
                        ctx.restore()

                        // warm cream body with blush
                        var bodyGrad = ctx.createLinearGradient(-r, -r, r, r)
                        bodyGrad.addColorStop(0.0, "rgba(255,250,240,0.96)")
                        bodyGrad.addColorStop(0.5, "rgba(255,245,235,0.98)")
                        bodyGrad.addColorStop(1.0, "rgba(255,230,220,0.92)")
                        ctx.fillStyle = bodyGrad
                        ctx.beginPath()
                        ctx.arc(0, 0, r, 0, 2 * Math.PI)
                        ctx.fill()
                        ctx.strokeStyle = "rgba(200,190,180,0.3)"
                        ctx.lineWidth = 1
                        ctx.stroke()

                        // face
                        ctx.strokeStyle = "rgb(40,40,60)"
                        ctx.lineWidth = Math.max(1.2, r * 0.1)
                        ctx.lineCap = "round"
                        ctx.lineJoin = "round"

                        if (seed === 0) {
                            // >w< squinty face
                            ctx.beginPath()
                            ctx.moveTo(-r * 0.45, -r * 0.25); ctx.lineTo(-r * 0.2, -r * 0.05); ctx.lineTo(-r * 0.45, r * 0.15)
                            ctx.stroke()
                            ctx.beginPath()
                            ctx.moveTo(r * 0.45, -r * 0.25); ctx.lineTo(r * 0.2, -r * 0.05); ctx.lineTo(r * 0.45, r * 0.15)
                            ctx.stroke()
                            // w mouth
                            ctx.beginPath()
                            ctx.moveTo(-r * 0.2, r * 0.2)
                            ctx.quadraticCurveTo(-r * 0.1, r * 0.35, 0, r * 0.22)
                            ctx.quadraticCurveTo(r * 0.1, r * 0.35, r * 0.2, r * 0.2)
                            ctx.stroke()
                            // pink tongue
                            ctx.fillStyle = "rgb(240,130,140)"
                            ctx.beginPath()
                            ctx.arc(0, r * 0.3, r * 0.07, 0, 2 * Math.PI)
                            ctx.fill()
                        } else if (seed === 1) {
                            // ˆ_ˆ happy closed eyes
                            ctx.beginPath()
                            ctx.arc(-r * 0.28, -r * 0.12, r * 0.17, Math.PI, 2 * Math.PI)
                            ctx.stroke()
                            ctx.beginPath()
                            ctx.arc(r * 0.28, -r * 0.12, r * 0.17, Math.PI, 2 * Math.PI)
                            ctx.stroke()
                            // smile
                            ctx.beginPath()
                            ctx.arc(0, r * 0.15, r * 0.15, 0, Math.PI)
                            ctx.stroke()
                        } else {
                            // dot eyes, o mouth (surprised peeking)
                            ctx.fillStyle = "rgb(40,40,60)"
                            ctx.beginPath(); ctx.arc(-r * 0.25, -r * 0.1, r * 0.08, 0, 2 * Math.PI); ctx.fill()
                            ctx.beginPath(); ctx.arc(r * 0.25, -r * 0.1, r * 0.08, 0, 2 * Math.PI); ctx.fill()
                            ctx.beginPath(); ctx.arc(0, r * 0.2, r * 0.1, 0, 2 * Math.PI); ctx.stroke()
                        }

                        // ring front half
                        ctx.save()
                        ctx.rotate(ringAng)
                        ctx.scale(1, 0.26)
                        ctx.strokeStyle = grad
                        ctx.lineWidth = r * 0.3
                        ctx.beginPath()
                        ctx.arc(0, 0, r * 1.9, 0, Math.PI)
                        ctx.stroke()
                        ctx.restore()

                        ctx.restore()
                    }

                    blobPlanet(width - 38, 30, 18, 0)
                    blobPlanet(width * 0.32, 16, 8, 1)
                    blobPlanet(6, height * 0.6, 6, 2)
                }
            }

            // -- clearBlack scenery ---------------------------------------
            // clearBlack ships no bitmap decoration at all — the whole skin
            // is one crosshair hitcircle with a full-spectrum rainbow ring
            // and a matching approach circle, on a true-black playfield.
            // The scene leans entirely on that one motif: three of those
            // hitcircles looping their own approach circles, plus a
            // drifting cursor with the skin's blue-violet glow.

            Canvas {
                id: clearblackScene
                anchors.fill: parent
                visible: root.clearblack
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
                Connections { target: hub; function onThemeChanged() { clearblackScene.requestPaint() } }

                // phase: 0..1 approach-circle loop; rot: slow ring/cursor drift
                property real phase: 0
                NumberAnimation on phase { from: 0; to: 1; duration: 1700; loops: Animation.Infinite; running: clearblackScene.visible }
                property real rot: 0
                NumberAnimation on rot { from: 0; to: Math.PI * 2; duration: 6000; loops: Animation.Infinite; running: clearblackScene.visible }
                onPhaseChanged: requestPaint()
                onRotChanged: requestPaint()

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    function rainbowRing(cx, cy, r, rotOffset) {
                        var segs = 40
                        ctx.lineWidth = Math.max(1.6, r * 0.14)
                        for (var i = 0; i < segs; i++) {
                            var a0 = rot + rotOffset + (i / segs) * Math.PI * 2
                            var a1 = rot + rotOffset + ((i + 1.05) / segs) * Math.PI * 2
                            ctx.strokeStyle = Qt.hsva(i / segs, 0.7, 1.0, 1.0)
                            ctx.beginPath()
                            ctx.arc(cx, cy, r, a0, a1)
                            ctx.stroke()
                        }
                    }

                    function hitcircle(cx, cy, r, seed) {
                        // approach circle: shrinks in, fades in, then loops
                        var ph = (phase + seed * 0.33) % 1.0
                        var ar = r * (2.15 - 1.15 * ph)
                        ctx.strokeStyle = root.ink
                        ctx.globalAlpha = Math.min(1.0, ph * 2.2) * 0.8
                        ctx.lineWidth = 1.1
                        ctx.beginPath(); ctx.arc(cx, cy, ar, 0, 2 * Math.PI); ctx.stroke()
                        ctx.globalAlpha = 1

                        // near-black body occludes the star field behind it
                        ctx.fillStyle = root.paper
                        ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI); ctx.fill()

                        rainbowRing(cx, cy, r, seed * 1.7)

                        ctx.strokeStyle = root.ink
                        ctx.globalAlpha = 0.82
                        ctx.lineWidth = 1.0
                        ctx.beginPath(); ctx.arc(cx, cy, r * 0.88, 0, 2 * Math.PI); ctx.stroke()
                        ctx.globalAlpha = 1

                        // soft glow behind the crosshair
                        ctx.fillStyle = root.accent
                        ctx.globalAlpha = 0.3
                        ctx.beginPath(); ctx.arc(cx, cy, r * 0.5, 0, 2 * Math.PI); ctx.fill()
                        ctx.globalAlpha = 1

                        ctx.strokeStyle = root.ink
                        ctx.lineWidth = 1.4
                        var cs = r * 0.22
                        ctx.beginPath(); ctx.moveTo(cx - cs, cy); ctx.lineTo(cx + cs, cy); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(cx, cy - cs); ctx.lineTo(cx, cy + cs); ctx.stroke()
                    }

                    hitcircle(width - 40, 30, 18, 0)
                    hitcircle(width * 0.30, 15, 9, 1)
                    hitcircle(10, height * 0.64, 6, 2)

                    // wandering cursor glow, like the skin's cursor.png
                    function cursorPos(tt) {
                        return [width * (0.18 + 0.64 * (0.5 + 0.5 * Math.sin(tt * 0.7))),
                                height * (0.68 + 0.16 * Math.sin(tt * 1.1 + 1.3))]
                    }
                    ctx.strokeStyle = root.accent
                    ctx.globalAlpha = 0.3
                    ctx.lineWidth = 1.2
                    ctx.beginPath()
                    for (var i = 8; i >= 0; i--) {
                        var tp = cursorPos(rot - i * 0.12)
                        if (i === 8) ctx.moveTo(tp[0], tp[1]); else ctx.lineTo(tp[0], tp[1])
                    }
                    ctx.stroke()
                    ctx.globalAlpha = 1

                    var cp = cursorPos(rot)
                    ctx.fillStyle = root.accent
                    ctx.globalAlpha = 0.5
                    ctx.beginPath(); ctx.arc(cp[0], cp[1], 6, 0, 2 * Math.PI); ctx.fill()
                    ctx.globalAlpha = 1
                    ctx.fillStyle = root.ink
                    ctx.beginPath(); ctx.arc(cp[0], cp[1], 2.2, 0, 2 * Math.PI); ctx.fill()
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
        id: quicksand
        source: hub.pastelFontPath
    }
    FontLoader {
        id: freedomFont
        source: hub.freedomFontPath
    }
}
