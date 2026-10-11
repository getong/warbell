#!/bin/sh
# masonry_set.sh <download dir>   (needs ImageMagick 7 `magick`)
# Castle kit (castle_kit.py / castle_kit.glb) scanned sets from Poly Haven 2K scans
# (<id>_{diff,nor_gl,rough,ao,disp}_2k.jpg, all CC0, Rob Tuytel):
#   s_ashlar  <- medieval_blocks_03  coursed ashlar (2 m tile, 5 courses), graded from its sandstone
#                yellow-brown to a pale grey-beige limestone: OUR fresh stone tier
#   s_rubble  <- broken_wall         rough coursed rubble / fieldstone (3 m tile), greyer: the OLD
#                COLONY ruins + bell tower (vertex colour adds the moss and damp at the foot)
#   s_shingle <- roof_slates_02      weathered split shingles (3 m tile), darkened: keep/tower roofs
# -> assets/forest_pbr/<set>_{albedo,normal,ormh}.png (1024^2). Then pack:
#   cargo run --release --example pack_forest_textures      (packs every loose PNG in forest_pbr)
set -e
D="$1"
O="$(dirname "$0")/../../assets/forest_pbr"
one() {
  id="$1"; set_="$2"; mod="$3"
  magick "$D/${id}_diff_2k.jpg" -resize 1024x1024 -modulate "$mod" -depth 8 -define png:color-type=2 "$O/${set_}_albedo.png"
  magick "$D/${id}_nor_gl_2k.jpg" -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/${set_}_normal.png"
  magick "$D/${id}_ao_2k.jpg" -colorspace Gray -resize 1024x1024 "$O/_ao.png"
  magick "$D/${id}_rough_2k.jpg" -colorspace Gray -resize 1024x1024 "$O/_r.png"
  magick "$D/${id}_disp_2k.jpg" -colorspace Gray -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
  magick "$O/_r.png" -fx 0 "$O/_m.png"
  magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/${set_}_ormh.png"
  rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
  echo "$set_ albedo: $(magick "$O/${set_}_albedo.png" -format '%[fx:mean.r*255] %[fx:mean.g*255] %[fx:mean.b*255]' info:)"
}
# limestone: brighter, most of the sandstone's yellow taken out
one medieval_blocks_03 s_ashlar 170,40
# old colony rubble: a touch brighter, cooler grey
one broken_wall s_rubble 122,62
# shingle: darker, weathered silver-brown
one roof_slates_02 s_shingle 72,75
