#!/bin/bash

echo -e "file 'file:${1}.mp4'\nfile 'file:${2}.mp4'" | ffmpeg -hide_banner -f concat -safe 0 -protocol_whitelist 'file,pipe,fd' -i - -map '0:0' '-c:0' copy '-disposition:0' default -map '0:1' '-c:1' copy '-disposition:1' default -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale 90000 -f mp4 -y test-p$3.mp4
