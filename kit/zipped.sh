#!/bin/bash

function log() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  echo -e "${timestamp} ${input_string}" >>zip.log
}

function compress() {
  log "###### Ready to compress video: $1"
  ffmpeg -i $1.mp4 -preset veryfast -maxrate 8000k -bufsize 1.6M -c:a copy ${1}-zipped.mp4
  log "###### Done for compressing ${1}.\n"
}

compress $1
