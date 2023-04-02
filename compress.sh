#!/bin/bash

o="test"

function log {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  echo -e "${timestamp} ${input_string}" >> ${o}_cut.log
}

idx=1

function compress {
  log "Ready to compress video: $1"
  echo "ffmpeg -i $1 -preset veryfast -maxrate 8000k -bufsize 1.6M -c:a copy ${o}-with_total_${idx}_zipped.mp4"
  log "###### Done for compressing ${o}.\n"
}

xx=$1
compress $xx
