#!/bin/sh
# snow_set.sh <download dir>   (needs ImageMagick 7 `magick`)
# Poly Haven snow_02 2K scan (<id>_{diff,nor_gl,rough,ao,disp}_2k.jpg, CC0)
# -> the kit's `s_snow` PBR set (assets/forest_pbr/s_snow_{albedo,normal,ormh}.png, 1024^2), worn by the
# drifts / snow caps of the cold story scenes (stories_cold.py). Then pack:
#   cargo run --release --example pack_forest_textures      (packs every loose PNG in forest_pbr)
set -e
D="$1"
O="$(dirname "$0")/../../assets/forest_pbr"
id=snow_02
# Same lift as the alpine snow layer (alpine_scans.sh): the scan is shot dim (mean sRGB 0.65) -> fresh
# snow (~0.90 sRGB) keeping ~45% of its contrast, a hint cool. The models' vertex colour adds the
# blue in the shaded folds. AO lifted (the scan bakes heavy footprint shading).
magick "$D/${id}_diff_2k.jpg" -filter Box -resize 1024x1024 -fx "0.90 + (u - 0.648) * 0.45" -channel R -evaluate multiply 0.985 -channel B -evaluate multiply 1.012 +channel -depth 8 -define png:color-type=2 "$O/s_snow_albedo.png"
magick "$D/${id}_nor_gl_2k.jpg" -filter Box -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/s_snow_normal.png"
magick "$D/${id}_ao_2k.jpg" -colorspace Gray -filter Box -resize 1024x1024 -fx "0.55 + 0.45 * u" "$O/_ao.png"
magick "$D/${id}_rough_2k.jpg" -colorspace Gray -filter Box -resize 1024x1024 "$O/_r.png"
magick "$D/${id}_disp_2k.jpg" -colorspace Gray -filter Box -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
magick "$O/_r.png" -fx 0 "$O/_m.png"
magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/s_snow_ormh.png"
rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
echo "s_snow albedo: $(magick "$O/s_snow_albedo.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b]' info:)  ormh: $(magick "$O/s_snow_ormh.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b] %[fx:mean.a]' info:)"
