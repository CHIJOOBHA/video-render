#!/bin/bash
# Encode one rendered piece into its final HD and SD form on the chunk machine itself (same settings as before,
# so quality is unchanged), then upload both next to the raw piece. Usage: finalize_piece.sh <chunk.mp4> <r2 dir>
set -e
C=$1; D=$2; B=$(basename "$C")
command -v ffmpeg >/dev/null || { sudo apt-get -qq update && sudo apt-get -qq install -y ffmpeg >/dev/null; }
ffmpeg -v error -y -i "$C" -an -c:v libx264 -preset medium -tune animation -crf 22 -maxrate 3M -bufsize 6M -pix_fmt yuv420p "hd-$B"
ffmpeg -v error -y -i "$C" -an -vf scale=-2:480 -c:v libx264 -preset veryfast -crf 26 -profile:v main -pix_fmt yuv420p "sd-$B"
python3 "$GITHUB_WORKSPACE/r2.py" put "hd-$B" "$D/hd-$B"
python3 "$GITHUB_WORKSPACE/r2.py" put "sd-$B" "$D/sd-$B"
