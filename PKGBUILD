# Maintainer: dzejkop <jakub.muzik07@gmail.com>
pkgname=osusayohub
pkgver=0.1.0
pkgrel=6
pkgdesc="osu!lazer overlay (live PP, hit-error/UR meter) and SayoDevice O3C configuration hub"
arch=('any')
url="https://github.com/dzejkop/osusayohub"
license=('MIT')
depends=(
  'python'
  'python-pyqt6'
  'python-qasync'
  'python-websockets'
  'python-evdev'
  'python-hidapi'
  'qt6-declarative'
  'layer-shell-qt'
)
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=()

pkgver() {
  cd "$startdir"
  grep -Po '(?<=^version = ")[^"]+' pyproject.toml
}

build() {
  cd "$startdir"
  python -m build --wheel --no-isolation --outdir "$srcdir/dist"
}

package() {
  python -m installer --destdir="$pkgdir" "$srcdir"/dist/*.whl
  install -Dm644 "$startdir/packaging/osusayohub.desktop" \
    "$pkgdir/usr/share/applications/osusayohub.desktop"
  install -Dm644 "$startdir/packaging/osusayohub.svg" \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/osusayohub.svg"
  install -Dm644 "$startdir/packaging/99-osusayohub.rules" \
    "$pkgdir/usr/lib/udev/rules.d/99-osusayohub.rules"
}
