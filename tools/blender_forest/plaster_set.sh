#!/bin/sh
# plaster_set.sh <download dir>   (needs ImageMagick 7 `magick`)
# Poly Haven white_rough_plaster 1K scan (<id>_{diff,nor_gl,rough,ao,disp}_1k.jpg, CC0): rough lime
# whitewash flaking off a darker daub in chips -> the town kit's `s_plaster` PBR set
# (assets/forest_pbr/s_plaster_{albedo,normal,ormh}.png, 1024^2), the infill of the timber-frame
# houses (town_kit.py). Graded to off-white KCD2 limewash: grey, the chips' contrast squeezed into
# the top of the range (+level), then multiplied by a warm cream so the mean lands near sRGB #d8d1c2
# (it must still read light in shade); roughness lifted to ~0.9 (matte lime), AO softened. The
# models' vertex colour adds only a little splash-back grime at the wall feet. Then pack:
#   cargo run --release --example pack_forest_textures      (packs every loose PNG in forest_pbr)
set -e
D="$1"
O="$(dirname "$0")/../../assets/forest_pbr"
id=white_rough_plaster
LO=${PLASTER_LO:-48}
magick "$D/${id}_diff_1k.jpg" -resize 1024x1024 -colorspace Gray +level "$LO%,100%" -colorspace sRGB \( +clone -fill "#fff7e5" -colorize 100 \) -compose multiply -composite -depth 8 -define png:color-type=2 "$O/s_plaster_albedo.png"
magick "$D/${id}_nor_gl_1k.jpg" -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/s_plaster_normal.png"
magick "$D/${id}_ao_1k.jpg" -colorspace Gray -resize 1024x1024 +level 70%,100% "$O/_ao.png"
magick "$D/${id}_rough_1k.jpg" -colorspace Gray -resize 1024x1024 +level 80%,98% "$O/_r.png"
magick "$D/${id}_disp_1k.jpg" -colorspace Gray -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
magick "$O/_r.png" -fx 0 "$O/_m.png"
magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/s_plaster_ormh.png"
rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
echo "s_plaster albedo: $(magick "$O/s_plaster_albedo.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b]' info:)  ormh: $(magick "$O/s_plaster_ormh.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b] %[fx:mean.a]' info:)"
