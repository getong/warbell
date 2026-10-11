#!/bin/sh
# cobble_set.sh <download dir>   (needs ImageMagick 7 `magick`)
# Poly Haven cobblestone_05 1K scan (<id>_{diff,nor_gl,rough,ao,disp}_1k.jpg, CC0, Rob Tuytel): rounded
# dark setts with earth in the joints -> the castle paving's `s_cobble` PBR set
# (assets/forest_pbr/s_cobble_{albedo,normal,ormh}.png, 1024^2), worn by the keep apron + gate passages
# (`castle::PAVED_RECTS`). The muddy joints let the paving sit in the trodden-mud yard. Then pack:
#   cargo run --release --example pack_forest_textures      (packs every loose PNG in forest_pbr)
set -e
D="$1"
O="$(dirname "$0")/../../assets/forest_pbr"
id=cobblestone_05
magick "$D/${id}_diff_1k.jpg" -resize 1024x1024 -modulate 96,88 -depth 8 -define png:color-type=2 "$O/s_cobble_albedo.png"
magick "$D/${id}_nor_gl_1k.jpg" -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/s_cobble_normal.png"
magick "$D/${id}_ao_1k.jpg" -colorspace Gray -resize 1024x1024 "$O/_ao.png"
magick "$D/${id}_rough_1k.jpg" -colorspace Gray -resize 1024x1024 "$O/_r.png"
magick "$D/${id}_disp_1k.jpg" -colorspace Gray -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
magick "$O/_r.png" -fx 0 "$O/_m.png"
magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/s_cobble_ormh.png"
rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
echo "s_cobble albedo: $(magick "$O/s_cobble_albedo.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b]' info:)  ormh: $(magick "$O/s_cobble_ormh.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b] %[fx:mean.a]' info:)"
