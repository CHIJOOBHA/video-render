#!/bin/bash
# Encode one rendered piece into its final HD and SD form on the chunk machine itself (same settings as before,
# so quality is unchanged), then upload both next to the raw piece. Usage: finalize_piece.sh <chunk.mp4> <r2 dir>
set -e
C=$1; D=$2; B=$(basename "$C")
# 6 Nov 2026: pieces hung for 30+ min here after rendering (apt-get on a slow mirror). Use Remotion's own ffmpeg (it has
# libx264 and is already installed beside the project); apt-get only as a last resort, and never longer than 5 min.
FF=ffmpeg
if ! command -v ffmpeg >/dev/null; then
  RF=$(ls -d node_modules/@remotion/compositor-linux-x64-gnu 2>/dev/null | head -1)
  if [ -n "$RF" ] && [ -x "$RF/ffmpeg" ]; then FF="$PWD/$RF/ffmpeg"; export LD_LIBRARY_PATH="$PWD/$RF${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  else timeout 300 sudo apt-get -qq update && timeout 300 sudo apt-get -qq install -y ffmpeg >/dev/null; fi
fi
"$FF" -v error -y -i "$C" -an -c:v libx264 -preset medium -tune animation -crf 22 -maxrate 3M -bufsize 6M -pix_fmt yuv420p "hd-$B"
"$FF" -v error -y -i "$C" -an -vf scale=-2:480 -c:v libx264 -preset veryfast -crf 26 -profile:v main -pix_fmt yuv420p "sd-$B"
python3 "$GITHUB_WORKSPACE/r2.py" put "hd-$B" "$D/hd-$B"
python3 "$GITHUB_WORKSPACE/r2.py" put "sd-$B" "$D/sd-$B"
