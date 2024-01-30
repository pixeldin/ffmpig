#!/bin/bash

# ffprobe -v error -read_intervals $s_ts%$e_ts -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $target.mp4 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2
ffprobe -v error -read_intervals 0%30 -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $1 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2
