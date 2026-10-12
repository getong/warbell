#!/bin/sh
# wild_set.sh <download dir>   (needs ImageMagick 7 `magick`)
# The swamp / rocky discovery sites' own scanned sets (wild_sites.py / wild_sites.glb), Poly Haven
# 2K scans (<id>_{diff,nor_gl,rough,ao,disp}_2k.jpg, all CC0). Each biome gets its own palette:
#   ROCKY  s_granite <- lichen_rock         lichen-crusted dark stone: the Old Ones' menhirs + rock door
#          s_slate   <- castle_wall_slates  dry-laid split slate: the colony signal tower, bridge piers
#   SWAMP  s_chapel  <- mossy_stone_wall    damp moss-jointed fieldstone: the sunken mission chapel
#          s_peat    <- mud_forest          wet black-brown peat: cut peat, grave mounds, bog skirts
#          s_rotwood <- weathered_planks    grey-black rotting timber: causeway, weir stakes, sledge
#          s_rust    <- rusty_metal_02      old iron gone to rust: lantern, hoops, chains, grave iron
# -> assets/forest_pbr/<set>_{albedo,normal,ormh}.png (1024^2). Then pack:
#   cargo run --release --example pack_forest_textures      (packs every loose PNG in forest_pbr)
set -e
D="$1"
O="$(dirname "$0")/../../assets/forest_pbr"
one() {
  id="$1"; set_="$2"; mod="$3"; extra="$4"
  magick "$D/${id}_diff_2k.jpg" -resize 1024x1024 -modulate "$mod" $extra -depth 8 -define png:color-type=2 "$O/${set_}_albedo.png"
  magick "$D/${id}_nor_gl_2k.jpg" -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/${set_}_normal.png"
  magick "$D/${id}_ao_2k.jpg" -colorspace Gray -resize 1024x1024 "$O/_ao.png"
  magick "$D/${id}_rough_2k.jpg" -colorspace Gray -resize 1024x1024 "$O/_r.png"
  magick "$D/${id}_disp_2k.jpg" -colorspace Gray -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
  magick "$O/_r.png" -fx 0 "$O/_m.png"
  magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/${set_}_ormh.png"
  rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
  echo "$set_ albedo: $(magick "$O/${set_}_albedo.png" -format '%[fx:mean.r*255] %[fx:mean.g*255] %[fx:mean.b*255]' info:)"
}
# granite: brighter, the scan's red-brown pulled to a cold blue-grey so the lichen reads on it
one lichen_rock s_granite 165,35,100
# slate: a touch darker and greyer than the sunlit scan
one castle_wall_slates s_slate 92,55,100
# chapel fieldstone: lifted a little, moss kept
one mossy_stone_wall s_chapel 118,85,100
# peat: lifted out of black, kept warm
one mud_forest s_peat 125,80,100
# rotten timber: kept dark, greyed (the vertex colour adds the green damp at the foot)
one weathered_planks s_rotwood 100,45,100
# rust: the scan's pale paint taken down to old iron, the rust kept orange-brown
one rusty_metal_02 s_rust 48,90,100
