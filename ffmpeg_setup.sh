#!/bin/bash
# 6 Nov 2026: apt-get on a slow Ubuntu mirror hung renders for 30+ min. ffmpeg (+ ffprobe) from apt with a 4-minute limit,
# else the static build from PyPI (static-ffmpeg). Usage: bash ffmpeg_setup.sh [extra apt packages]
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && [ -z "$1" ] && exit 0
if timeout 240 sudo apt-get -qq update && timeout 240 sudo apt-get -qq install -y ffmpeg "$@" >/dev/null; then exit 0; fi
echo "apt slow - using the static ffmpeg"
sudo python3 -m pip install -q --break-system-packages static-ffmpeg
static_ffmpeg_paths >/dev/null 2>&1 || python3 -c "import static_ffmpeg; static_ffmpeg.add_paths()"
D=$(python3 -c "import static_ffmpeg.run as r; print(r.get_or_fetch_platform_executables_else_raise()[0].rsplit('/',1)[0])")
sudo ln -sf "$D/ffmpeg" /usr/local/bin/ffmpeg; sudo ln -sf "$D/ffprobe" /usr/local/bin/ffprobe
ffmpeg -version | head -1
