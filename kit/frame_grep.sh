#!/bin/bash

number=$1
end=$(expr "$number" + 4)
echo "grep pts: $number, $end"
# 范围读取关键帧数据并解析为数组
IFS=$'\n' input=($(ffprobe -v error -read_intervals "${number}%${end}" -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv $2 | grep -A 4 -B 4 --no-group-separator "K" |sort -n -t ',' -k 2))

prev=""
K_FRAME=""
BEF_FRAME=""
for i in "${!input[@]}"; do
  row="${input[$i]}"
  #echo "line:======== $row"
  col=$(echo "$row" | awk -F ',' '{printf "%.6f,%s", $2, $3}')
  col1=$(echo "$col" | awk -F ',' '{print $1}')
  col2=$(echo "$col" | awk -F ',' '{print $2}')
  #echo "col:======== $col1 / $col2"
  # should prepare bc.exe extention first
  if [[ $col2 == *"K"* && $(echo "$col1 >= $number" | bc) -eq 1 ]]; then
    K_FRAME=$col1
    BEF_FRAME=$prev
    break
  fi
  prev=$(echo "$row" | awk -F ',' '{printf "%.6f", $2}')
done

# Reformat: key frame, before key frame
echo -e "K_FRAME / BEF_FRAME : $K_FRAME / $BEF_FRAME"
