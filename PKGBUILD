# Maintainer: dzejkop <jakub.muzik07@gmail.com>
pkgname=ppeek
pkgver=0.5.0
pkgrel=1
pkgdesc="osu!lazer overlay: live PP, hit-error/UR meter, KPS"
arch=('any')
url="https://github.com/cavalinho-xdd/ppeek"
license=('MIT')
conflicts=('osusayohub')
replaces=('osusayohub')
depends=(
  'python'
  'python-pyqt6'
  'python-qasync'
  'python-websockets'
  'python-evdev'
  'python-psutil'
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
  install -Dm644 "$startdir/packaging/ppeek.desktop" \
    "$pkgdir/usr/share/applications/ppeek.desktop"
  install -Dm644 "$startdir/packaging/ppeek.svg" \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/ppeek.svg"
  install -Dm644 "$startdir/packaging/99-ppeek.rules" \
    "$pkgdir/usr/lib/udev/rules.d/99-ppeek.rules"
}
