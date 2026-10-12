#!/bin/sh
# biome_sites_set.sh <download dir>   (needs ImageMagick 7 `magick`)
# Poly Haven 2K scans (CC0) -> the PBR sets worn by the desert / forest story sites (sites_warm.py):
#   s_sandstone  <- sandstone_cracks      wind-scoured ochre sandstone (arches, slabs, the glyph wall)
#   s_tile       <- blue_floor_tiles_01   coursed tiles; vertex colour glazes them turquoise / cracks them
#   s_mosswood   <- moss_wood             rotten, moss-furred oak (graves, the sawpit, kiln cordwood)
#   s_clay       <- clay_plaster          fired / unfired clay (the bell mould, the furnace, jars)
#   s_mossrock   <- mossy_rock            lichen-and-moss stone (the Old Ones' pillar, kiln stones)
# The download dir holds <id>_{diff,nor_gl,rough,ao,disp}_2k.{jpg,png}; mossy_rock falls back to
# $PH_SRC/textures/mossy_rock. Then pack: cargo run --release --example pack_forest_textures
set -e
D="$1"
O="$(dirname "$0")/../../assets/forest_pbr"
PH="${PH_SRC:-C:/Users/skibi/Documents/Codex/polyhaven_src}"

src() { # src <id> <map>
  for f in "$D/$1_$2_2k.jpg" "$D/$1_$2_2k.png" "$PH/textures/$1/$1_$2_2k.png" "$PH/textures/$1/$1_$2_2k.jpg"; do
    [ -f "$f" ] && { echo "$f"; return; }
  done
  echo "missing $1 $2" >&2; exit 1
}

# set <out> <id> <albedo -fx expr> <ao floor>
set_one() {
  out=$1; id=$2; fx=$3; aof=$4
  magick "$(src $id diff)" -filter Box -resize 1024x1024 -fx "$fx" -depth 8 -define png:color-type=2 "$O/${out}_albedo.png"
  magick "$(src $id nor_gl)" -filter Box -resize 1024x1024 -depth 8 -define png:color-type=2 "$O/${out}_normal.png"
  if f=$(src $id ao 2>/dev/null); then
    magick "$f" -colorspace Gray -filter Box -resize 1024x1024 -fx "$aof + (1 - $aof) * u" "$O/_ao.png"
  else
    magick -size 1024x1024 xc:white -colorspace Gray "$O/_ao.png"
  fi
  magick "$(src $id rough)" -colorspace Gray -filter Box -resize 1024x1024 "$O/_r.png"
  magick "$(src $id disp)" -colorspace Gray -filter Box -resize 1024x1024 -contrast-stretch 0.5%x0.5% "$O/_h.png"
  magick "$O/_r.png" -fx 0 "$O/_m.png"
  magick "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png" -set colorspace sRGB -combine -alpha on -depth 8 -define png:color-type=6 "$O/${out}_ormh.png"
  rm -f "$O/_ao.png" "$O/_r.png" "$O/_m.png" "$O/_h.png"
  echo "$out albedo: $(magick "$O/${out}_albedo.png" -format '%[fx:mean.r] %[fx:mean.g] %[fx:mean.b]' info:)"
}

# Sandstone: keep the scan's warmth, lift it a touch (the vertex colour sun-bleaches crowns).
set_one s_sandstone sandstone_cracks "u * 1.04" 0.5
# Tiles: desaturate toward a neutral glaze base (the vertex colour paints the turquoise / ochre).
set_one s_tile blue_floor_tiles_01 "0.62 + (u - 0.55) * 0.9" 0.45
set_one s_mosswood moss_wood "u" 0.45
# Clay: neutral-ish mid tone so the vertex colour reads as terracotta (fired) or grey-brown (raw).
set_one s_clay clay_plaster "0.6 + (u - 0.38) * 1.4" 0.5
set_one s_mossrock mossy_rock "u" 0.45
