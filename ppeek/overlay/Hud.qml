import QtQuick

// The HUD panel itself: themed scenery behind the live numbers.
// Window-agnostic — hosted by Overlay.qml (wlr-layer-shell), PlainOverlay.qml
// (frameless always-on-top window) and overlay/preview.py (offscreen grabs
// for the settings cards and README screenshots). Expects a `hub` context
// property (bridge.HubState).
//
// Layout ("variant A"): PP hero + grade badge on top, combo / accuracy /
// KPS as labelled columns, the hit-error meter, then hit counts and UR in
// the footer. Scenery keeps out of the text boxes in `textRects`: fixed
// motifs sit in the free band between PP and grade, scattered particles
// are placed by spot(), which rejects anything landing on text.
//
// Skin-driven scenes (see overlay/theme.py):
//  - night:      Fool Moon Night — hand-drawn ink sky, planets, moon, ripples
//  - pastel:     Arona & Plana — red halo + string, stripes, diamonds
//  - freedom:    FREEDOM DiVE REiMAGINED — blob planets, rainbow arrows, BTMC tag
//  - clearblack: clearBlack — rainbow-ring hitcircles, drifting cursor glow
Item {
    id: hud
    width: 300
    height: 150

    // false in previews: every animation holds still so a grab is stable
    readonly property bool animated: hub.animated

    readonly property bool pastel: hub.scene === "pastel"
    readonly property bool night: hub.scene === "night"
    readonly property bool freedom: hub.scene === "freedom"
    readonly property bool clearblack: hub.scene === "clearblack"
    readonly property color ink: hub.ink
    readonly property color inkDim: hub.inkDim
    readonly property color paper: hub.paper
    readonly property color accent: hub.accent
    readonly property color decoRed: hub.decoRed
    readonly property color blood: hub.missColor
    readonly property string fontFamily: hub.themeFont

    // pastel grade inks — cartoonish but muted, so they sit in every scene
    readonly property var gradeColors: ({
        "SS": "#e9d18b",   // soft gold
        "S":  "#9fc6ea",   // pastel blue
        "A":  "#a9d9a2",   // pastel green
        "B":  "#eab98c",   // pastel orange
        "C":  "#e29a9a",   // washed rose
        "D":  "#c84040"    // blood red
    })

    // hit-error windows in ms; the meter spans ±110 ms
    readonly property real errRange: 110
    readonly property var windows: [16, 64, 97]   // 300 / 100 / 50
    function judgementColor(pos) {
        var ms = Math.abs(pos) * errRange
        if (ms <= windows[0]) return ink
        if (ms <= windows[1]) return hub.hit100Color
        if (ms <= windows[2]) return hub.hit50Color
        return blood
    }

    // -- scenery placement -------------------------------------------------

    // boxes particles keep out of: [x, y, w, h] — the live numbers, plus
    // the band between PP and grade where each scene's fixed motifs sit
    readonly property var textRects: [
        [10, 2, 152, 48],                 // PP
        [width - 56, 4, 50, 46],          // grade badge
        [160, 0, 84, 50],                 // scene motifs
        [12, 54, 82, 38],                 // combo
        [104, 54, 96, 38],                // accuracy
        [196, 54, 44, 38],                // KPS
        [10, 99, width - 20, 20],         // hit-error meter
        [10, 124, 126, 24],               // hit counts
        [width - 80, 124, 74, 24]         // UR
    ]

    // deterministic hash in [0, 1) — Math.random would reshuffle the
    // scenery on every load and make previews differ from the overlay
    function rnd(seed) {
        var x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453
        return x - Math.floor(x)
    }

    function onText(x, y, pad) {
        for (var i = 0; i < textRects.length; i++) {
            var r = textRects[i]
            if (x > r[0] - pad && x < r[0] + r[2] + pad && y > r[1] - pad && y < r[1] + r[3] + pad)
                return true
        }
        return false
    }

    // stable pseudo-random point clear of the numbers; a particle that
    // finds no free spot is parked off-panel rather than over text
    function spot(i, salt) {
        for (var k = 0; k < 64; k++) {
            var x = 6 + rnd(i * 97.1 + k * 13.7 + salt) * (width - 12)
            var y = 5 + rnd(i * 31.3 + k * 7.9 + salt * 1.7) * (height - 10)
            if (!onText(x, y, 6))
                return Qt.point(x, y)
        }
        return Qt.point(-20, -20)
    }

    // the hits row and UR can grow; footer motifs centre in the gap between
    readonly property real footerGapX: (hitsRow.x + hitsRow.width + urRow.x) / 2

    // -- frame ---------------------------------------------------------------
    // each skin tribute gets its own panel look (OverlayTheme.frame):
    //  rounded: plain card (color palettes)
    //  sketch:  FOOL MOON NIGHT — square, hand-inked edges that "boil"
    //           (redrawn from a few jittered takes, like hand animation)
    //  painted: FREEDOM DiVE REiMAGINED — watercolor nebula, no hard edge
    //  archive: Arona & Plana — Blue Archive card with a cut corner
    //  minimal: clearBlack — hard-edged hairline box

    readonly property string frame: hub.frame
    readonly property bool sketch: frame === "sketch"

    // which jittered take of the hand-drawn lines is showing
    property int boil: 0
    Timer {
        interval: 170
        repeat: true
        running: hud.sketch && hud.animated && hud.visible
        onTriggered: hud.boil = (hud.boil + 1) % 3
    }

    // wobbly hand-drawn helpers for sketch Canvas items; `take` picks the
    // jitter so every boil frame is a different but stable drawing
    function inkLine(ctx, x0, y0, x1, y1, take, amp) {
        var len = Math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0))
        var ux = (x1 - x0) / len, uy = (y1 - y0) / len
        var seed = x0 * 3.1 + y0 * 7.7 + x1 * 1.3 + y1 * 5.9 + take * 101
        // strokes overshoot their ends a little, like a quick pen
        var o0 = 2 + rnd(seed) * 5, o1 = 2 + rnd(seed + 1) * 5
        var sx = x0 - ux * o0, sy = y0 - uy * o0
        var n = Math.max(2, Math.round((len + o0 + o1) / 14))
        ctx.beginPath()
        ctx.moveTo(sx, sy)
        for (var i = 1; i <= n; i++) {
            var f = i / n
            var d = (rnd(seed + i * 2.3) - 0.5) * 2 * amp
            ctx.lineTo(sx + ux * (len + o0 + o1) * f - uy * d,
                       sy + uy * (len + o0 + o1) * f + ux * d)
        }
        ctx.stroke()
    }

    function inkCircle(ctx, cx, cy, r, take, amp) {
        var seed = cx * 1.7 + cy * 3.3 + r * 9.1 + take * 37
        var n = Math.max(10, Math.round(r * 1.4))
        var start = rnd(seed) * Math.PI * 2
        ctx.beginPath()
        // a little past a full turn, so the pen's start and end overlap
        for (var i = 0; i <= n + 2; i++) {
            var a = start + i / n * Math.PI * 2
            var rr = r + (rnd(seed + i * 1.9) - 0.5) * 2 * amp
            var x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
        }
        ctx.stroke()
    }

    Item {
        id: panel
        anchors.fill: parent

        // rounded card (color palettes)
        Rectangle {
            anchors.fill: parent
            visible: hud.frame === "rounded"
            radius: 10
            gradient: Gradient {
                GradientStop { position: 0.0; color: hub.bgTop }
                GradientStop { position: 1.0; color: hub.bgBottom }
            }
            border.color: Qt.alpha(hud.ink, 0.28)
            border.width: 1
        }

        // hairline box (clearBlack)
        Rectangle {
            anchors.fill: parent
            visible: hud.frame === "minimal"
            gradient: Gradient {
                GradientStop { position: 0.0; color: hub.bgTop }
                GradientStop { position: 1.0; color: hub.bgBottom }
            }
            border.color: Qt.alpha(hud.ink, 0.22)
            border.width: 1
        }

        // FOOL MOON NIGHT: ink on black, grainy, scratchy edges
        Canvas {
            id: sketchFrame
            anchors.fill: parent
            visible: hud.sketch
            onVisibleChanged: if (visible) requestPaint()
            Component.onCompleted: requestPaint()
            Connections {
                target: hud
                function onBoilChanged() { if (sketchFrame.visible) sketchFrame.requestPaint() }
            }
            Connections { target: hub; function onThemeChanged() { sketchFrame.requestPaint() } }
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var ink = hud.ink
                function inkA(a) { return Qt.rgba(ink.r, ink.g, ink.b, a) }
                var w = width, h = height, m = 4

                var g = ctx.createLinearGradient(0, 0, 0, h)
                g.addColorStop(0, hub.bgTop)
                g.addColorStop(1, hub.bgBottom)
                ctx.fillStyle = g
                ctx.fillRect(m - 1, m - 1, w - 2 * m + 2, h - 2 * m + 2)

                // paper grain + a few chalky scratches (fixed, they don't boil)
                for (var i = 0; i < 260; i++) {
                    ctx.fillStyle = inkA(0.03 + hud.rnd(i + 0.31) * 0.09)
                    ctx.fillRect(m + hud.rnd(i + 0.11) * (w - 2 * m),
                                 m + hud.rnd(i + 0.21) * (h - 2 * m), 1, 1)
                }
                ctx.lineWidth = 0.7
                var scratches = [[16, 118, 34, 112], [252, 132, 270, 127], [232, 16, 247, 9], [9, 60, 13, 47]]
                for (var k = 0; k < scratches.length; k++) {
                    var sc = scratches[k]
                    ctx.strokeStyle = inkA(0.12)
                    hud.inkLine(ctx, sc[0], sc[1], sc[2], sc[3], 0, 0.6)
                }

                // the edges: a heavy pass and a lighter second pass, each wobbling
                var t = hud.boil
                var edges = [[m, m, w - m, m], [w - m, m, w - m, h - m],
                             [w - m, h - m, m, h - m], [m, h - m, m, m]]
                ctx.lineCap = "round"
                ctx.lineJoin = "round"
                for (var e = 0; e < edges.length; e++) {
                    var ed = edges[e]
                    ctx.strokeStyle = inkA(0.9)
                    ctx.lineWidth = 1.5
                    hud.inkLine(ctx, ed[0], ed[1], ed[2], ed[3], t, 0.9)
                    ctx.strokeStyle = inkA(0.4)
                    ctx.lineWidth = 0.8
                    hud.inkLine(ctx, ed[0] + 1.5, ed[1] + 1.2, ed[2] + 1.5, ed[3] + 1.2, t + 7, 1.3)
                }
            }
        }

        // FREEDOM DiVE REiMAGINED: watercolor nebula fading out at the edges
        Canvas {
            id: paintedFrame
            anchors.fill: parent
            visible: hud.frame === "painted"
            onVisibleChanged: if (visible) requestPaint()
            Component.onCompleted: requestPaint()
            Connections { target: hub; function onThemeChanged() { paintedFrame.requestPaint() } }
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var w = width, h = height

                ctx.fillStyle = hub.bgBottom
                ctx.fillRect(0, 0, w, h)

                // soft overlapping washes: deep blue, teal, a touch of violet
                function wash(cx, cy, r, rgb, a) {
                    var g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
                    g.addColorStop(0, Qt.rgba(rgb[0], rgb[1], rgb[2], a))
                    g.addColorStop(1, Qt.rgba(rgb[0], rgb[1], rgb[2], 0))
                    ctx.fillStyle = g
                    ctx.fillRect(0, 0, w, h)
                }
                wash(w * 0.72, h * 0.25, 150, [0.16, 0.32, 0.66], 0.75)
                wash(w * 0.18, h * 0.85, 120, [0.10, 0.36, 0.55], 0.55)
                wash(w * 0.45, h * 0.05, 90, [0.36, 0.30, 0.70], 0.35)
                wash(w * 0.95, h * 0.95, 80, [0.08, 0.20, 0.45], 0.5)
                // brushy blotches give the wash a painted grain
                for (var i = 0; i < 70; i++) {
                    var bx = hud.rnd(i + 0.13) * w, by = hud.rnd(i + 0.27) * h
                    var br = 4 + hud.rnd(i + 0.41) * 16
                    var light = hud.rnd(i + 0.55) > 0.5
                    wash(bx, by, br, light ? [0.55, 0.75, 1.0] : [0.02, 0.04, 0.14],
                         0.05 + hud.rnd(i + 0.69) * 0.07)
                }
                // far bokeh stars, the deepest layer
                for (var j = 0; j < 26; j++) {
                    var sx = hud.rnd(j + 3.1) * w, sy = hud.rnd(j + 3.3) * h
                    var sr = 0.4 + hud.rnd(j + 3.7) * 1.1
                    ctx.fillStyle = Qt.rgba(0.85, 0.92, 1.0, 0.25 + hud.rnd(j + 3.9) * 0.4)
                    ctx.beginPath(); ctx.arc(sx, sy, sr, 0, 2 * Math.PI); ctx.fill()
                }

                // feather all four edges to transparent: no hard border
                ctx.globalCompositeOperation = "destination-out"
                var f = 14
                function fade(x0, y0, x1, y1, rx, ry, rw, rh) {
                    var g = ctx.createLinearGradient(x0, y0, x1, y1)
                    g.addColorStop(0, "rgba(0,0,0,1)")
                    g.addColorStop(1, "rgba(0,0,0,0)")
                    ctx.fillStyle = g
                    ctx.fillRect(rx, ry, rw, rh)
                }
                fade(0, 0, 0, f, 0, 0, w, f)
                fade(0, h, 0, h - f, 0, h - f, w, f)
                fade(0, 0, f, 0, 0, 0, f, h)
                fade(w, 0, w - f, 0, w - f, 0, f, h)
                ctx.globalCompositeOperation = "source-over"
            }
        }

        // Arona & Plana: Blue Archive UI card — cut top-right corner with
        // accent bars along the cut and a bright tab on the top edge
        Canvas {
            id: archiveFrame
            anchors.fill: parent
            visible: hud.frame === "archive"
            onVisibleChanged: if (visible) requestPaint()
            Component.onCompleted: requestPaint()
            Connections { target: hub; function onThemeChanged() { archiveFrame.requestPaint() } }
            readonly property real cut: 24
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var w = width - 1, h = height - 1, c = cut
                var ac = hud.accent

                ctx.beginPath()
                ctx.moveTo(0.5, 0.5)
                ctx.lineTo(w - c, 0.5)
                ctx.lineTo(w, c)
                ctx.lineTo(w, h)
                ctx.lineTo(0.5, h)
                ctx.closePath()
                var g = ctx.createLinearGradient(0, 0, 0, h)
                g.addColorStop(0, hub.bgTop)
                g.addColorStop(1, hub.bgBottom)
                ctx.fillStyle = g
                ctx.fill()
                ctx.strokeStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.45)
                ctx.lineWidth = 1
                ctx.stroke()

                // accent bars echoing the cut, stepping inward
                for (var i = 0; i < 3; i++) {
                    var d = 6 + i * 6
                    ctx.strokeStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.7 - i * 0.2)
                    ctx.lineWidth = 2.5 - i * 0.6
                    ctx.beginPath()
                    ctx.moveTo(w - c - d + 4, 3)
                    ctx.lineTo(w - 3, c + d - 4)
                    ctx.stroke()
                }

                // the tab: a slanted bright strip on the top edge
                ctx.fillStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.9)
                ctx.beginPath()
                ctx.moveTo(14, 0.5)
                ctx.lineTo(72, 0.5)
                ctx.lineTo(69, 3.5)
                ctx.lineTo(11, 3.5)
                ctx.closePath()
                ctx.fill()
                // and a small slanted marker on the bottom edge
                ctx.fillStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.55)
                ctx.beginPath()
                ctx.moveTo(w - 46, h)
                ctx.lineTo(w - 14, h)
                ctx.lineTo(w - 17, h - 3)
                ctx.lineTo(w - 43, h - 3)
                ctx.closePath()
                ctx.fill()
            }
        }

        Item {
            id: scenery
            anchors.fill: parent
            anchors.margins: 1
            clip: true

            // -- FOOL MOON NIGHT --------------------------------------------

            // twinkling star field
            Repeater {
                model: hud.night ? 14 : 0
                Rectangle {
                    readonly property point p: hud.spot(index, 11)
                    readonly property real s: 0.5 + hud.rnd(index + 0.3) * 1.0
                    x: p.x - s; y: p.y - s
                    width: s * 2; height: s * 2; radius: s
                    color: hud.ink
                    opacity: 0.15 + 0.5 * hud.rnd(index + 0.7)
                    SequentialAnimation on opacity {
                        running: hud.animated
                        loops: Animation.Infinite
                        PauseAnimation { duration: hud.rnd(index + 1.1) * 2200 }
                        NumberAnimation { to: 0.85; duration: 500 + hud.rnd(index + 1.5) * 900; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.12; duration: 500 + hud.rnd(index + 1.9) * 900; easing.type: Easing.InOutSine }
                    }
                }
            }

            // four-point sparkle stars, like the hand-drawn sky
            Repeater {
                model: hud.night ? 3 : 0
                Item {
                    readonly property point p: hud.spot(index, 23)
                    x: p.x; y: p.y
                    opacity: 0.55
                    Rectangle { x: -4; y: -0.5; width: 8; height: 1; color: hud.ink }
                    Rectangle { x: -0.5; y: -4; width: 1; height: 8; color: hud.ink }
                    SequentialAnimation on opacity {
                        running: hud.animated
                        loops: Animation.Infinite
                        PauseAnimation { duration: hud.rnd(index + 2.3) * 3000 }
                        NumberAnimation { to: 0.8; duration: 700 + hud.rnd(index + 2.7) * 700; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.2; duration: 700 + hud.rnd(index + 3.1) * 700; easing.type: Easing.InOutSine }
                    }
                }
            }

            // hatched planets + crescent moon, in the band between PP and grade
            Canvas {
                id: nightScene
                anchors.fill: parent
                visible: hud.night
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
                Connections { target: hub; function onThemeChanged() { nightScene.requestPaint() } }
                Connections {
                    target: hud
                    function onBoilChanged() { if (nightScene.visible && hud.sketch) nightScene.requestPaint() }
                }
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var ink = hud.ink
                    function inkA(a) { return Qt.rgba(ink.r, ink.g, ink.b, a) }

                    function ringHalf(cx, cy, r, alpha, a0, a1) {
                        ctx.save()
                        ctx.translate(cx, cy)
                        ctx.rotate(-18 * Math.PI / 180)
                        ctx.scale(1, 0.32)
                        ctx.strokeStyle = inkA(alpha * 0.9)
                        ctx.lineWidth = 1.2
                        var ks = [1.55, 1.75, 1.95]
                        for (var j = 0; j < ks.length; j++) {
                            ctx.beginPath()
                            if (hud.sketch) {
                                // hand-drawn rings: radius drifts along the stroke
                                var n = 16
                                for (var q = 0; q <= n; q++) {
                                    var a = a0 + (a1 - a0) * q / n
                                    var rr = r * ks[j] + (hud.rnd(j * 31 + q * 1.7 + hud.boil * 53) - 0.5) * 1.6
                                    if (q === 0) ctx.moveTo(Math.cos(a) * rr, Math.sin(a) * rr)
                                    else ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr)
                                }
                            } else {
                                ctx.arc(0, 0, r * ks[j], a0, a1)
                            }
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
                        ctx.fillStyle = hud.paper
                        ctx.fill()
                        ctx.strokeStyle = inkA(alpha * 0.5)
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
                        ctx.strokeStyle = inkA(alpha)
                        ctx.lineWidth = 1.3
                        if (hud.sketch) {
                            hud.inkCircle(ctx, cx, cy, r, hud.boil, 0.6)
                        } else {
                            ctx.beginPath()
                            ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                            ctx.stroke()
                        }
                        if (ringed)  // near half, in front of the body
                            ringHalf(cx, cy, r, alpha, 0, Math.PI)
                    }

                    function moon(cx, cy, r, alpha) {
                        ctx.save()
                        ctx.beginPath()
                        ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                        ctx.fillStyle = inkA(alpha * 0.85)
                        ctx.fill()
                        ctx.globalCompositeOperation = "destination-out"
                        ctx.beginPath()
                        ctx.arc(cx + r * 0.45, cy - r * 0.25, r * 0.85, 0, 2 * Math.PI)
                        ctx.fill()
                        ctx.globalCompositeOperation = "source-over"
                        ctx.strokeStyle = inkA(alpha)
                        ctx.lineWidth = 1
                        if (hud.sketch) {
                            hud.inkCircle(ctx, cx, cy, r, hud.boil, 0.5)
                        } else {
                            ctx.beginPath()
                            ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                            ctx.stroke()
                        }
                        ctx.restore()
                    }

                    planet(206, 27, 11, 0.55, true)
                    planet(172, 12, 4, 0.4, false)
                    moon(234, 11, 5, 0.7)
                }
            }

            // water ripples in the footer gap, drifting outward
            Canvas {
                id: ripples
                visible: hud.night
                x: hud.footerGapX - width / 2
                y: parent.height - height
                width: 120
                height: 18
                opacity: 0.4
                property real phase: 0.4
                NumberAnimation on phase { from: 0; to: 1; duration: 2200; loops: Animation.Infinite; running: ripples.visible && hud.animated }
                onPhaseChanged: requestPaint()
                Component.onCompleted: requestPaint()
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var ink = hud.ink
                    var cx = width / 2, cy = height - 1
                    var gap = 12, maxr = width / 2
                    for (var r0 = 6 + phase * gap; r0 < maxr; r0 += gap) {
                        var fade = 1 - r0 / maxr
                        ctx.strokeStyle = Qt.rgba(ink.r, ink.g, ink.b, 0.6 * fade)
                        ctx.lineWidth = 1
                        ctx.save()
                        ctx.translate(cx, cy)
                        ctx.scale(1, 0.22)
                        ctx.beginPath()
                        ctx.arc(0, 0, r0, Math.PI, 2 * Math.PI)
                        ctx.stroke()
                        ctx.restore()
                    }
                }
            }

            // -- ARONA & PLANA (Blue Archive motifs) -------------------------

            // corner stripe clusters, dot grid, red halo with a dangling heart
            Canvas {
                id: pastelScene
                anchors.fill: parent
                visible: hud.pastel
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
                            [0, -8, 20, 4, hud.ink, 0.18],
                            [5, -1, 32, 5, hud.accent, 0.28],
                            [-6, 6, 24, 4, hud.ink, 0.36],
                            [8, 12, 16, 3, hud.accent, 0.18],
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
                        ctx.fillStyle = hud.ink
                        ctx.globalAlpha = 0.4
                        for (var gy = 0; gy < 3; gy++)
                            for (var gx = 0; gx < 5; gx++) {
                                ctx.beginPath()
                                ctx.arc(x0 + gx * 4.5, y0 + gy * 4.5, 0.8, 0, 2 * Math.PI)
                                ctx.fill()
                            }
                        ctx.globalAlpha = 1
                    }

                    stripes(2, height - 2, 135)
                    dotGrid(214, 38)

                    // red string hanging off the halo, ending in a tiny heart
                    var hx = 176, hy = 44
                    ctx.strokeStyle = hud.decoRed
                    ctx.globalAlpha = 0.4
                    ctx.lineWidth = 1
                    ctx.beginPath()
                    ctx.moveTo(193, 22)
                    ctx.bezierCurveTo(180, 26, 186, 36, hx, hy - 1)
                    ctx.stroke()

                    ctx.fillStyle = hud.decoRed
                    ctx.globalAlpha = 0.7
                    ctx.beginPath()
                    ctx.moveTo(hx, hy + 2.4)
                    ctx.bezierCurveTo(hx - 3.2, hy - 0.6, hx - 1.7, hy - 2.8, hx, hy - 0.9)
                    ctx.bezierCurveTo(hx + 1.7, hy - 2.8, hx + 3.2, hy - 0.6, hx, hy + 2.4)
                    ctx.fill()

                    // Arona's red halo, tilted
                    ctx.save()
                    ctx.translate(206, 18)
                    ctx.rotate(-14 * Math.PI / 180)
                    ctx.scale(1, 0.35)
                    ctx.strokeStyle = hud.decoRed
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
                model: hud.pastel ? 7 : 0
                Rectangle {
                    readonly property point p: hud.spot(index, 41)
                    readonly property real s: 2.2 + hud.rnd(index + 4.1) * 2.4
                    x: p.x - s / 2; y: p.y - s / 2
                    width: s; height: s
                    rotation: 45
                    color: index % 4 === 3 ? hud.decoRed : hud.ink
                    opacity: 0.2 + 0.4 * hud.rnd(index + 4.4)
                    SequentialAnimation on opacity {
                        running: hud.animated
                        loops: Animation.Infinite
                        PauseAnimation { duration: hud.rnd(index + 4.7) * 2600 }
                        NumberAnimation { to: 0.7; duration: 600 + hud.rnd(index + 5.1) * 800; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.15; duration: 600 + hud.rnd(index + 5.5) * 800; easing.type: Easing.InOutSine }
                    }
                }
            }

            // slowly rotating hollow squares in the accent blue
            Repeater {
                model: hud.pastel ? 4 : 0
                Rectangle {
                    readonly property point p: hud.spot(index, 57)
                    readonly property real s: 5 + hud.rnd(index + 6.1) * 4
                    x: p.x - s / 2; y: p.y - s / 2
                    width: s; height: s
                    color: "transparent"
                    border.color: hud.accent
                    border.width: 1
                    opacity: 0.45
                    rotation: hud.rnd(index + 6.4) * 90
                    RotationAnimation on rotation {
                        running: hud.animated
                        from: hud.rnd(index + 6.4) * 90; to: 360
                        duration: 14000 + hud.rnd(index + 6.8) * 8000
                        loops: Animation.Infinite
                    }
                }
            }

            // -- FREEDOM DiVE REiMAGINED -------------------------------------

            Canvas {
                id: freedomScene
                anchors.fill: parent
                visible: hud.freedom
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
                property real t: 1.2
                NumberAnimation on t { from: 0; to: Math.PI * 2; duration: 4000; loops: Animation.Infinite; running: freedomScene.visible && hud.animated }
                onTChanged: requestPaint()
                Connections { target: hub; function onThemeChanged() { freedomScene.requestPaint() } }

                // confetti + sparkles, placed clear of the numbers
                readonly property var confetti: {
                    var out = []
                    for (var i = 0; i < 12; i++) {
                        var p = hud.spot(i, 71)
                        out.push({x: p.x, y: p.y, sz: 1.5 + hud.rnd(i + 7.1) * 2.0,
                                  ph: hud.rnd(i + 7.4) * 6.28, sp: 0.6 + hud.rnd(i + 7.7) * 1.2,
                                  rt: hud.rnd(i + 8.1) * 360})
                    }
                    return out
                }
                readonly property var sparkles: {
                    var out = []
                    for (var i = 0; i < 5; i++) {
                        var p = hud.spot(i, 89)
                        out.push({x: p.x, y: p.y, sz: 2.0 + hud.rnd(i + 9.1) * 2.0,
                                  ph: hud.rnd(i + 9.4) * 6.28, sp: 0.5 + hud.rnd(i + 9.7) * 1.1})
                    }
                    return out
                }

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    // faint rainbow shooting-star washes from two corners
                    function shootingArrow(x0, y0, x1, y1, thickness, seed) {
                        var pulse = 0.07 + 0.05 * Math.sin(t * 1.3 + seed * 2.5)
                        var grad = ctx.createLinearGradient(x0, y0, x1, y1)
                        grad.addColorStop(0.0, Qt.rgba(1.0, 0.31, 0.24, pulse))
                        grad.addColorStop(0.25, Qt.rgba(1.0, 0.78, 0.2, pulse))
                        grad.addColorStop(0.5, Qt.rgba(0.39, 0.9, 0.39, pulse))
                        grad.addColorStop(0.75, Qt.rgba(0.31, 0.71, 1.0, pulse))
                        grad.addColorStop(1.0, Qt.rgba(0.71, 0.39, 1.0, pulse))
                        ctx.strokeStyle = grad
                        ctx.lineWidth = thickness
                        ctx.lineCap = "round"
                        ctx.beginPath()
                        ctx.moveTo(x0, y0)
                        ctx.lineTo(x1, y1)
                        ctx.stroke()
                    }
                    shootingArrow(-8, height + 4, width * 0.42, height * 0.3, 12, 0)
                    shootingArrow(width + 8, -4, width * 0.58, height * 0.7, 9, 1)

                    // white diamond confetti
                    for (var ci = 0; ci < confetti.length; ci++) {
                        var c = confetti[ci]
                        var tw = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(t * c.sp + c.ph))
                        ctx.save()
                        ctx.translate(c.x, c.y)
                        ctx.rotate((c.rt + t * c.sp * 15) * Math.PI / 180)
                        ctx.fillStyle = Qt.rgba(1, 1, 1, 0.63 * tw)
                        var ss = c.sz * 0.7
                        ctx.fillRect(-ss / 2, -ss / 2, ss, ss)
                        ctx.restore()
                    }

                    // golden sparkle stars
                    for (var si = 0; si < sparkles.length; si++) {
                        var sk = sparkles[si]
                        var stw = 0.2 + 0.8 * (0.5 + 0.5 * Math.sin(t * sk.sp + sk.ph))
                        var gs = sk.sz * (0.8 + 1.2 * stw)
                        ctx.strokeStyle = Qt.rgba(1.0, 0.86, 0.31, 0.86 * stw)
                        ctx.lineWidth = 1.5
                        ctx.beginPath(); ctx.moveTo(sk.x - gs, sk.y); ctx.lineTo(sk.x + gs, sk.y); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(sk.x, sk.y - gs); ctx.lineTo(sk.x, sk.y + gs); ctx.stroke()
                        var ds = gs * 0.5
                        ctx.strokeStyle = Qt.rgba(1.0, 0.86, 0.31, 0.5 * stw)
                        ctx.lineWidth = 1.0
                        ctx.beginPath(); ctx.moveTo(sk.x - ds, sk.y - ds); ctx.lineTo(sk.x + ds, sk.y + ds); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(sk.x - ds, sk.y + ds); ctx.lineTo(sk.x + ds, sk.y - ds); ctx.stroke()
                    }

                    // cloud planets: soft fluffy bodies with a glow, ringed by a
                    // brush-stroke rainbow; `depth` 0..1 pushes one back into the
                    // haze (fainter glow, bluer, flatter), like the skin's art
                    function blobPlanet(cx, cy, r, seed, depth) {
                        ctx.save()
                        ctx.translate(cx, cy)
                        var pulse = Math.sin(t * 1.5 + seed) * 0.05
                        var wobble = Math.sin(t * 0.8 + seed * 1.7) * 0.07
                        ctx.rotate(wobble)
                        ctx.scale(1 + pulse, 1 - pulse)
                        var near = 1 - depth

                        // glow halo
                        var halo = ctx.createRadialGradient(0, 0, r * 0.6, 0, 0, r * 2.4)
                        halo.addColorStop(0, Qt.rgba(1.0, 0.93, 0.95, 0.38 * near))
                        halo.addColorStop(1, Qt.rgba(1.0, 0.93, 0.95, 0))
                        ctx.fillStyle = halo
                        ctx.beginPath(); ctx.arc(0, 0, r * 2.4, 0, 2 * Math.PI); ctx.fill()

                        var grad = ctx.createLinearGradient(-r * 2.2, 0, r * 2.2, 0)
                        grad.addColorStop(0.0, "rgb(255,100,60)")
                        grad.addColorStop(0.2, "rgb(255,200,50)")
                        grad.addColorStop(0.4, "rgb(100,230,100)")
                        grad.addColorStop(0.6, "rgb(80,220,255)")
                        grad.addColorStop(0.8, "rgb(100,120,255)")
                        grad.addColorStop(1.0, "rgb(200,100,255)")

                        var ringAng = (15 + t * 25 * (seed % 2 === 0 ? 1 : -1)) * Math.PI / 180

                        // brush-stroke ring half: white rim, rainbow body, sheen
                        function ringHalf(a0, a1) {
                            ctx.save()
                            ctx.rotate(ringAng)
                            ctx.scale(1, 0.3)
                            ctx.lineCap = "round"
                            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.85 * near + 0.1)
                            ctx.lineWidth = r * 0.55 + 2.5
                            ctx.beginPath(); ctx.arc(0, 0, r * 1.85, a0, a1); ctx.stroke()
                            ctx.strokeStyle = grad
                            ctx.lineWidth = r * 0.55
                            ctx.beginPath(); ctx.arc(0, 0, r * 1.85, a0, a1); ctx.stroke()
                            ctx.strokeStyle = "rgba(255,255,255,0.45)"
                            ctx.lineWidth = Math.max(0.8, r * 0.1)
                            ctx.beginPath(); ctx.arc(0, 0, r * 1.72, a0, a1); ctx.stroke()
                            ctx.restore()
                        }
                        ringHalf(Math.PI, 2 * Math.PI)

                        // fluffy rim: soft cream dabs breaking up the outline
                        for (var fi = 0; fi < 26; fi++) {
                            var fa = fi / 26 * Math.PI * 2 + seed
                            var fr = r * (0.88 + hud.rnd(seed * 17 + fi * 1.3) * 0.18)
                            var fx = Math.cos(fa) * fr, fy = Math.sin(fa) * fr
                            var fs = r * (0.22 + hud.rnd(seed * 23 + fi * 2.1) * 0.14)
                            var dab = ctx.createRadialGradient(fx, fy, 0, fx, fy, fs)
                            dab.addColorStop(0, "rgba(255,244,240,0.7)")
                            dab.addColorStop(1, "rgba(255,244,240,0)")
                            ctx.fillStyle = dab
                            ctx.beginPath(); ctx.arc(fx, fy, fs, 0, 2 * Math.PI); ctx.fill()
                        }

                        // body: lit from the top-left, peachy pink toward the edge
                        var bodyGrad = ctx.createRadialGradient(-r * 0.35, -r * 0.4, r * 0.1, 0, 0, r)
                        bodyGrad.addColorStop(0.0, "rgba(255,255,252,1)")
                        bodyGrad.addColorStop(0.6, "rgba(255,240,238,0.98)")
                        bodyGrad.addColorStop(1.0, "rgba(246,196,204,0.95)")
                        ctx.fillStyle = bodyGrad
                        ctx.beginPath(); ctx.arc(0, 0, r * 0.94, 0, 2 * Math.PI); ctx.fill()

                        // blush
                        ctx.fillStyle = "rgba(245,140,160,0.35)"
                        ctx.beginPath(); ctx.ellipse(-r * 0.62, r * 0.08, r * 0.36, r * 0.2); ctx.fill()
                        ctx.beginPath(); ctx.ellipse(r * 0.26, r * 0.08, r * 0.36, r * 0.2); ctx.fill()

                        // face
                        ctx.strokeStyle = "rgb(40,40,60)"
                        ctx.lineWidth = Math.max(1.0, r * 0.1)
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
                            ctx.beginPath()
                            ctx.moveTo(-r * 0.2, r * 0.2)
                            ctx.quadraticCurveTo(-r * 0.1, r * 0.35, 0, r * 0.22)
                            ctx.quadraticCurveTo(r * 0.1, r * 0.35, r * 0.2, r * 0.2)
                            ctx.stroke()
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

                        ringHalf(0, Math.PI)

                        // atmospheric haze over distant planets
                        if (depth > 0) {
                            ctx.fillStyle = Qt.rgba(0.12, 0.22, 0.5, 0.5 * depth)
                            ctx.beginPath(); ctx.arc(0, 0, r * 1.02, 0, 2 * Math.PI); ctx.fill()
                        }

                        ctx.restore()
                    }

                    // far to near, so the big one paints over the haze
                    blobPlanet(16, 97, 4, 2, 0.7)
                    blobPlanet(171, 12, 5.5, 1, 0.45)
                    blobPlanet(204, 27, 15, 0, 0)
                }
            }

            // the skin's BTMC tag, bobbing in the footer gap
            Rectangle {
                id: btmcTag
                visible: hud.freedom
                x: hud.footerGapX - width / 2
                y: parent.height - height - 9 + bob
                width: btmcText.implicitWidth + 14
                height: btmcText.implicitHeight + 4
                radius: 4
                rotation: -4
                color: Qt.rgba(16 / 255, 24 / 255, 58 / 255, 0.92)
                border.color: Qt.rgba(150 / 255, 230 / 255, 1.0, 0.35)
                border.width: 1
                property real bob: 0
                SequentialAnimation on bob {
                    running: btmcTag.visible && hud.animated
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.2; duration: 1400; easing.type: Easing.InOutSine }
                    NumberAnimation { to: -1.2; duration: 1400; easing.type: Easing.InOutSine }
                }
                Text {
                    id: btmcText
                    anchors.centerIn: parent
                    text: "BTMC"
                    color: "white"
                    font.family: hud.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                    style: Text.Raised
                    styleColor: Qt.rgba(120 / 255, 210 / 255, 1.0, 0.45)
                }
            }

            // -- clearBlack --------------------------------------------------
            // the whole skin is one crosshair hitcircle with a full-spectrum
            // rainbow ring and approach circle on true black; the scene loops
            // three of those plus the skin's blue-violet cursor glow

            Canvas {
                id: clearblackScene
                anchors.fill: parent
                visible: hud.clearblack
                onVisibleChanged: if (visible) requestPaint()
                Component.onCompleted: requestPaint()
                Connections { target: hub; function onThemeChanged() { clearblackScene.requestPaint() } }

                // phase: 0..1 approach-circle loop; rot: slow ring/cursor drift
                property real phase: 0.6
                NumberAnimation on phase { from: 0; to: 1; duration: 1700; loops: Animation.Infinite; running: clearblackScene.visible && hud.animated }
                property real rot: 1.4
                NumberAnimation on rot { from: 0; to: Math.PI * 2; duration: 6000; loops: Animation.Infinite; running: clearblackScene.visible && hud.animated }
                onPhaseChanged: requestPaint()
                onRotChanged: requestPaint()

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    function rainbowRing(cx, cy, r, rotOffset) {
                        var segs = 40
                        ctx.lineWidth = Math.max(1.4, r * 0.14)
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
                        ctx.strokeStyle = hud.ink
                        ctx.globalAlpha = Math.min(1.0, ph * 2.2) * 0.6
                        ctx.lineWidth = 1.1
                        ctx.beginPath(); ctx.arc(cx, cy, ar, 0, 2 * Math.PI); ctx.stroke()
                        ctx.globalAlpha = 1

                        // near-black body occludes the star field behind it
                        ctx.fillStyle = hud.paper
                        ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI); ctx.fill()

                        rainbowRing(cx, cy, r, seed * 1.7)

                        ctx.strokeStyle = hud.ink
                        ctx.globalAlpha = 0.82
                        ctx.lineWidth = 1.0
                        ctx.beginPath(); ctx.arc(cx, cy, r * 0.88, 0, 2 * Math.PI); ctx.stroke()
                        ctx.globalAlpha = 1

                        // soft glow behind the crosshair
                        ctx.fillStyle = hud.accent
                        ctx.globalAlpha = 0.3
                        ctx.beginPath(); ctx.arc(cx, cy, r * 0.5, 0, 2 * Math.PI); ctx.fill()
                        ctx.globalAlpha = 1

                        ctx.strokeStyle = hud.ink
                        ctx.lineWidth = 1.3
                        var cs = r * 0.22
                        ctx.beginPath(); ctx.moveTo(cx - cs, cy); ctx.lineTo(cx + cs, cy); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(cx, cy - cs); ctx.lineTo(cx, cy + cs); ctx.stroke()
                    }

                    hitcircle(206, 26, 12, 0)
                    hitcircle(172, 12, 5, 1)
                    hitcircle(5, 97, 5, 2)

                    // cursor glow wandering through the footer gap
                    var gx = hud.footerGapX
                    function cursorPos(tt) {
                        return [gx + 26 * Math.sin(tt * 0.7),
                                height - 13 + 4 * Math.sin(tt * 1.1 + 1.3)]
                    }
                    ctx.strokeStyle = hud.accent
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
                    ctx.fillStyle = hud.accent
                    ctx.globalAlpha = 0.5
                    ctx.beginPath(); ctx.arc(cp[0], cp[1], 5, 0, 2 * Math.PI); ctx.fill()
                    ctx.globalAlpha = 1
                    ctx.fillStyle = hud.ink
                    ctx.beginPath(); ctx.arc(cp[0], cp[1], 2, 0, 2 * Math.PI); ctx.fill()
                }
            }

            // sketchbook corner brackets, on the hard-edged frames
            Repeater {
                model: [
                    { cx: 6,  cy: 6,  dx: 1,  dy: 1 },
                    { cx: scenery.width - 6, cy: 6, dx: -1, dy: 1 },
                    { cx: 6,  cy: scenery.height - 6, dx: 1, dy: -1 },
                    { cx: scenery.width - 6, cy: scenery.height - 6, dx: -1, dy: -1 }
                ]
                Item {
                    x: modelData.cx; y: modelData.cy
                    visible: hud.frame === "rounded" || hud.frame === "minimal" || hud.sketch
                    opacity: 0.4
                    Rectangle { x: modelData.dx > 0 ? 0 : -8; y: 0; width: 8; height: 1; color: hud.ink }
                    Rectangle { x: 0; y: modelData.dy > 0 ? 0 : -8; width: 1; height: 8; color: hud.ink }
                }
            }
        }

        // -- live numbers --------------------------------------------------
        // hidden while tosu isn't attached, so the "waiting" notice
        // doesn't sit on top of a panel full of zeroes
        Item {
            anchors.fill: parent
            visible: hub.connected

            // PP hero, with the unit set smaller so the number leads
            Row {
                x: 14; y: 2
                spacing: 2
                Text {
                    id: ppText
                    color: hud.ink
                    font.family: hud.fontFamily
                    font.pixelSize: 40
                    font.bold: true
                    property real shownPp: hub.pp
                    Behavior on shownPp {
                        enabled: hud.animated
                        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                    }
                    text: Math.round(shownPp)
                }
                Text {
                    anchors.baseline: ppText.baseline
                    color: hud.inkDim
                    font.family: hud.fontFamily
                    font.pixelSize: 20
                    font.bold: true
                    text: "pp"
                }
            }

            // grade badge — ring and letter in the rank's pastel ink
            Item {
                id: gradeBadge
                visible: hub.grade !== ""
                x: hud.width - width - 14
                y: 9
                width: 38; height: 38
                readonly property color tint: hud.gradeColors[hub.grade] || hud.ink
                // circle on most frames, a square on clearBlack's hard box, a
                // Blue Archive diamond on Arona,
                // a hand-inked boiling ring on FOOL MOON NIGHT
                Rectangle {
                    anchors.fill: parent
                    visible: !hud.sketch
                    radius: hud.frame === "minimal" ? 3 : hud.frame === "archive" ? 5 : width / 2
                    rotation: hud.frame === "archive" ? 45 : 0
                    scale: hud.frame === "archive" ? 0.78 : 1
                    color: Qt.alpha(gradeBadge.tint, 0.12)
                    border.color: gradeBadge.tint
                    border.width: 1.5
                    Behavior on border.color { ColorAnimation { duration: 350 } }
                }
                Canvas {
                    id: inkRing
                    anchors.fill: parent
                    anchors.margins: -3
                    visible: hud.sketch
                    property color tint: gradeBadge.tint
                    onTintChanged: requestPaint()
                    onVisibleChanged: if (visible) requestPaint()
                    Component.onCompleted: requestPaint()
                    Connections {
                        target: hud
                        function onBoilChanged() { if (inkRing.visible) inkRing.requestPaint() }
                    }
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.lineCap = "round"
                        ctx.strokeStyle = tint
                        ctx.lineWidth = 1.5
                        hud.inkCircle(ctx, width / 2, height / 2, width / 2 - 4, hud.boil, 0.9)
                        ctx.strokeStyle = Qt.alpha(tint, 0.45)
                        ctx.lineWidth = 0.8
                        hud.inkCircle(ctx, width / 2 + 1, height / 2 + 0.5, width / 2 - 4.5, hud.boil + 5, 1.2)
                    }
                }
                Text {
                    id: gradeText
                    anchors.centerIn: parent
                    color: gradeBadge.tint
                    font.family: hud.fontFamily
                    font.pixelSize: hub.grade.length > 1 ? 18 : 24
                    font.bold: true
                    text: hub.grade
                    Behavior on color { ColorAnimation { duration: 350 } }
                    // little pop when the rank changes
                    onTextChanged: if (hud.animated) gradePop.restart()
                    SequentialAnimation {
                        id: gradePop
                        NumberAnimation { target: gradeBadge; property: "scale"; to: 1.25; duration: 70 }
                        NumberAnimation { target: gradeBadge; property: "scale"; to: 1.0; duration: 200; easing.type: Easing.OutBack }
                    }
                }
            }

            // combo / accuracy / KPS — value over a small label
            Row {
                x: 14; y: 54
                Repeater {
                    model: [
                        { key: "combo", label: "COMBO" },
                        { key: "acc", label: "ACC" },
                        { key: "kps", label: "KPS" }
                    ]
                    Column {
                        width: (hud.width - 28) / 3
                        spacing: -2
                        Text {
                            id: statValue
                            color: hud.ink
                            font.family: hud.fontFamily
                            font.pixelSize: 21
                            text: modelData.key === "combo" ? hub.combo + "x"
                                : modelData.key === "acc" ? hub.accuracy.toFixed(2) + "%"
                                : hub.kps.toFixed(0)
                            transformOrigin: Item.Left
                            // combo pops when it grows
                            property int last: 0
                            Connections {
                                target: hub
                                enabled: modelData.key === "combo"
                                function onFrameChanged() {
                                    if (hub.combo > statValue.last && hud.animated)
                                        comboPop.restart()
                                    statValue.last = hub.combo
                                }
                            }
                            SequentialAnimation {
                                id: comboPop
                                NumberAnimation { target: statValue; property: "scale"; to: 1.18; duration: 60 }
                                NumberAnimation { target: statValue; property: "scale"; to: 1.0; duration: 160; easing.type: Easing.OutCubic }
                            }
                        }
                        Text {
                            color: hud.inkDim
                            font.family: hud.fontFamily
                            font.pixelSize: 10
                            font.letterSpacing: 1.5
                            text: modelData.label
                        }
                    }
                }
            }

            // hit-error meter — judgement windows as tinted bands
            Item {
                id: meter
                x: 14; y: 101
                width: hud.width - 28
                height: 16

                Repeater {
                    // widest first so the narrower windows layer on top
                    model: [
                        { ms: hud.windows[2], tint: hub.hit50Color, o: 0.16 },
                        { ms: hud.windows[1], tint: hub.hit100Color, o: 0.2 },
                        { ms: hud.windows[0], tint: hud.ink, o: 0.45 }
                    ]
                    Rectangle {
                        readonly property real half: (modelData.ms / hud.errRange) * meter.width / 2
                        x: meter.width / 2 - half
                        y: meter.height / 2 - 2
                        width: half * 2
                        height: 4
                        radius: 2
                        color: modelData.tint
                        opacity: modelData.o
                    }
                }

                Rectangle {  // center line
                    x: meter.width / 2 - 1
                    width: 2; height: meter.height
                    radius: 1
                    color: hud.ink
                }

                Repeater {  // recent hits, colored by the window they landed in
                    model: hub.errorTicks
                    Rectangle {
                        x: meter.width / 2 + modelData.pos * meter.width / 2 - 1
                        y: 2
                        width: 2
                        height: meter.height - 4
                        color: hud.judgementColor(modelData.pos)
                        opacity: 0.9 * (1.0 - modelData.age)
                    }
                }
            }

            // hit counts: 300 · 100 · 50 · miss, each in its judgement color
            Row {
                id: hitsRow
                x: 14
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                spacing: 6
                component Count: Text {
                    font.family: hud.fontFamily
                    font.pixelSize: 15
                }
                // drawn, not a glyph: hand-drawn fonts put "·" on the baseline
                component Dot: Item {
                    width: 3; height: hitsRow.height
                    Rectangle {
                        anchors.centerIn: parent
                        width: 3; height: 3; radius: 1.5
                        color: hud.inkDim
                    }
                }
                Count { color: hud.ink; text: hub.hits300 }
                Dot {}
                Count { color: hub.hit100Color; text: hub.hits100 }
                Dot {}
                Count { color: hub.hit50Color; text: hub.hits50 }
                Dot {}
                Count { color: hud.blood; text: hub.hitsMiss }
            }

            Row {
                id: urRow
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                spacing: 6
                Text {
                    anchors.baseline: urValue.baseline
                    color: hud.inkDim
                    font.family: hud.fontFamily
                    font.pixelSize: 10
                    font.letterSpacing: 1.5
                    text: "UR"
                }
                Text {
                    id: urValue
                    color: hud.ink
                    font.family: hud.fontFamily
                    font.pixelSize: 15
                    text: hub.ur.toFixed(1)
                }
            }
        }

        Column {
            anchors.centerIn: parent
            visible: !hub.connected
            spacing: 2
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: hud.ink
                font.family: hud.fontFamily
                font.pixelSize: 18
                text: "waiting for osu!"
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: hud.inkDim
                font.family: hud.fontFamily
                font.pixelSize: 11
                font.letterSpacing: 1.5
                text: "TOSU NOT ATTACHED"
            }
        }
    }
}
