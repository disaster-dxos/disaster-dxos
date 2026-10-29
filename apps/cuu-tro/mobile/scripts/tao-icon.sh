#!/usr/bin/env sh
# SPDX-License-Identifier: Apache-2.0
# Sinh biểu tượng app Android (mipmap) và iOS (AppIcon) từ logo dùng chung của repo docs/images/logo/mark.png.
# Nền trắng + lề 12 % (nhận diện: biểu tượng có vùng trong suốt, không đặt thẳng lên nền màu); iOS không cho
# kênh alpha nên làm phẳng trên nền trắng. Cần ImageMagick 7 (`magick`). Chạy: yarn icons
set -eu
cd "$(dirname "$0")/.."
GOC=../../../docs/images/logo/mark.png
command -v magick >/dev/null 2>&1 || { echo "Cần ImageMagick 7 (lệnh magick)" >&2; exit 1; }

ve() { # ve <cạnh px> <tệp ra> [tron]
  canh=$1; ra=$2
  noi=$((canh * 76 / 100))
  if [ "${3:-}" = tron ]; then
    magick -size "${canh}x${canh}" xc:none -fill white -draw "circle $((canh / 2)),$((canh / 2)) $((canh / 2)),0" \
      \( "$GOC" -resize "${noi}x${noi}" \) -gravity center -composite -depth 8 "$ra"
  else
    magick -size "${canh}x${canh}" xc:white \( "$GOC" -resize "${noi}x${noi}" \) -gravity center -composite \
      -alpha remove -alpha off -depth 8 "$ra"
  fi
}

for d in mdpi:48 hdpi:72 xhdpi:96 xxhdpi:144 xxxhdpi:192; do
  ten=${d%%:*}; canh=${d#*:}
  ve "$canh" "android/app/src/main/res/mipmap-$ten/ic_launcher.png"
  ve "$canh" "android/app/src/main/res/mipmap-$ten/ic_launcher_round.png" tron
done

IOS=ios/CuuTroHienTruong/Images.xcassets/AppIcon.appiconset
for c in 40 58 60 80 87 120 180 1024; do
  ve "$c" "$IOS/icon-$c.png"
done
echo "Đã sinh biểu tượng từ $GOC"
