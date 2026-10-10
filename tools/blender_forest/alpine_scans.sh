#!/bin/sh
# alpine_scans.sh <download dir> <out dir>   (needs ImageMagick 7 `magick`)
# Poly Haven 2K scans (snow_02, rock_face, gray_rocks: <id>_{diff,nor_gl,rough,ao,disp}_2k.jpg)
# -> 1024^2 alpine layer PNGs (albedo sRGB / normal GL / ormh linear) for layers 0 / 3 / 2, then:
#   ALPINE_SRC=<out dir> PACK_ONLY=alpine cargo run --release --example pack_forest_textures
# The meadow layer (1, from alpine.py) is kept byte-for-byte from the existing alpine_*.dds.
set -e
D="$1"
O="$2"
mkdir -p "$O"

# name  id          albedo-fx (sRGB space, per channel; u = input)
layer() {
  name="$1"; id="$2"; fx="$3"; aofx="$4"; rt="$5"; bt="$6"
  magick "$D/${id}_diff_2k.jpg" -filter Box -resize 1024x1024 -fx "$fx" -channel R -evaluate multiply "$rt" -channel B -evaluate multiply "$bt" +channel -depth 8 -define png:color-type=2 "$O/alpine_${name}_albedo.png"
  magick "$D/${id}_nor_gl_2k.jpg" -filter Box -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/alpine_${name}_normal.png"
  magick "$D/${id}_ao_2k.jpg" -colorspace Gray -filter Box -resize 1024x1024 -fx "$aofx" "$O/_ao.png"
  magick "$D/${id}_rough_2k.jpg" -colorspace Gray -filter Box -resize 1024x1024 "$O/_r.png"
  magick "$D/${id}_disp_2k.jpg" -colorspace Gray -filter Box -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
  magick "$O/_r.png" -fx 0 "$O/_m.png"
  magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/alpine_${name}_ormh.png"
  rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
  echo "$name albedo: $(magick "$O/alpine_${name}_albedo.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b]' info:)  ormh: $(magick "$O/alpine_${name}_ormh.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b] %[fx:mean.a]' info:)"
}

# Snow: the scan is shot dim (mean sRGB 0.65); lift to fresh-snow albedo (~0.90 sRGB, linear ~0.78)
# keeping ~45% of its contrast, a hint cool. AO lifted (the scan bakes heavy footprint shading).
layer snow snow_02 "0.90 + (u - 0.648) * 0.45" "0.55 + 0.45 * u" 0.985 1.012
# Cliff rock: warm brown scan -> cold lichen-grey granite (desaturated, slightly brighter).
layer rock rock_face "lum = 0.30*u.r + 0.59*u.g + 0.11*u.b; (lum + (u - lum) * 0.28) * 1.12" "u" 0.97 1.04
# Scree: grey talus, mostly desaturated, a touch cool.
layer scree gray_rocks "lum = 0.30*u.r + 0.59*u.g + 0.11*u.b; lum + (u - lum) * 0.40" "0.25 + 0.75 * u" 0.98 1.03
