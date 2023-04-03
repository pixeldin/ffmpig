#!/bin/bash

ffprobe -v error -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $1 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2
