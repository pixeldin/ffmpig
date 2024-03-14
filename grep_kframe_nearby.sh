#!/bin/bash

# ffprobe -v error -read_intervals $s_ts%$e_ts -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $target.mp4 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2

#ffprobe -v error -read_intervals $2%$3 -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $1 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2

if [ "$1" == "-o" ] && [ "$3" == "-s" ] && [ "$5" == "-e" ]; then
    ffprobe -v error -read_intervals ${4}%${6} -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $2 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2 
else
    echo "示例用法: grep_key_frame.sh -o demo.mp4 -s 0 -e 30"
fi
