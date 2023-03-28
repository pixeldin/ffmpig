#!/bin/bash

if [ $# -lt 3 ]; then
    echo "Usage: `basename $0` input_1.mp4 input_2.mp4 ... output.mp4"
    exit 0
fi

# determine all arguments
ARGS=("$@")
# get the last argument (output file)
output=${ARGS[${#ARGS[@]}-1]}
# drop it from the array
unset ARGS[${#ARGS[@]}-1]

(for f in "${ARGS[@]}"; do echo "file file:'$f'"; done) | ffmpeg -protocol_whitelist file,pipe -f concat -safe 0 -i pipe: -vcodec copy -acodec copy $output
