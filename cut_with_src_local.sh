#!/bin/bash
#set -x

usage() {
  echo "Usage: $0 [-o 文件名前缀] [-m 切割片段, 如'00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33']" 1>&2
  exit 1
}

while getopts ":o:m:" args; do
  case "${args}" in
  o)
    o=${OPTARG}
    ;;
  m)
    m=${OPTARG}
    ;;
  *)
    usage
    ;;
  esac
done

if [ -z "${o}" ] || [ -z "${m}" ]; then
  usage
  exit -1
fi

FILE_PREFIX=${o}

function log() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  echo -e "${timestamp} ${input_string}" >>${o}_cut.log
}

# $filename
function get_total_rate_of() {
  echo $(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 ${FILE_PREFIX}.mp4)
}

# 视频总帧数
TR=$(get_total_rate_of)

function get_file_size() {
  if [ -f "$1" ]; then
    local size=$(du -h "$1" | cut -f 1)
    echo "Size: $size"
  else
    echo "file not exists."
  fi
}

# grep_for_key_and_before $timestamps
function grep_for_key_and_before() {
  local start=$1
  local end=$(expr "$start" + 4)
  log "Grep pts, from $start(s) to $end(s)"
  # 范围读取关键帧数据并解析为数组
  IFS=$'\n' input=($(ffprobe -v error -read_intervals "${start}%${end}" -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv ${FILE_PREFIX}.mp4 | grep -B 4 --no-group-separator "K" | sort -n -t ',' -k 2))

  K_FRAME=""
  BEF_KEY_FRAME=""

  local prev=""
  for i in "${!input[@]}"; do
    row="${input[$i]}"    
    col=$(echo "$row" | awk -F ',' '{printf "%.6f,%s", $2, $3}')
    col1=$(echo "$col" | awk -F ',' '{print $1}')
    col2=$(echo "$col" | awk -F ',' '{print $2}')
    
    # should prepare bc.exe extention first
    if [[ $col2 == *"K"* && $(echo "$col1 >= $start" | bc) -eq 1 ]]; then
      K_FRAME=$col1
      BEF_KEY_FRAME=$prev
      break
    fi
    prev=$(echo "$row" | awk -F ',' '{printf "%.6f", $2}')
  done

  # 当前秒关键帧的前一帧不在同一秒,则忽略
  if [ -z "$BEF_KEY_FRAME" ] || [ $(echo "$BEF_KEY_FRAME <= $start" | bc) -eq 1 ]; then
    log "Second time at $start(s) >= $BEF_KEY_FRAME(BEF_KEY_FRAME), reset as -1"
    BEF_KEY_FRAME="-1"
  fi

  log "Ready to process $1(s) result info: $K_FRAME(K_FRAME) / $BEF_KEY_FRAME(BEF_KEY_FRAME)"
}

# cut from src $K_FRAME $end
function cut_after() {
  local duration=$(echo "scale=5; ${2}-${1}" | bc | sed 's/^\./0./')  
  #echo "After cut duration: $duration, prefix: $FILE_PREFIX"
  ffmpeg -hide_banner -ss $1 -i $FILE_PREFIX.mp4 -t $duration -map '0:0' '-c:0' copy -map '0:1' '-c:1' copy -map_metadata 0 -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale 90000 -f mp4 -y $FILE_PREFIX-smartcut-segment-copyed-tmp.mp4
}

# cut from src $start $BEF_KEY_FRAME
function cut_before() {
  local duration=$(echo "scale=5; ${2}-${1}" | bc | sed 's/^\./0./')  
  #echo "After cut duration: $duration, prefix: $FILE_PREFIX, TR: $TR"
  ffmpeg -hide_banner -ss $1 -i ${FILE_PREFIX}.mp4 -ss 0 -t $duration -map '0:0' '-c:0' h264 '-b:0' $TR -map '0:1' '-c:1' copy -ignore_unknown -video_track_timescale 90000 -f mp4 -y $FILE_PREFIX-smartcut-segment-encoded-tmp.mp4
}

# 合并非关键帧(前)与关键帧时段(后) $encoded $coped $idx
function merge_nokey_before_with_key() {  
  echo -e "file 'file:${1}.mp4'\nfile 'file:${2}.mp4'" | ffmpeg -hide_banner -f concat -safe 0 -protocol_whitelist 'file,pipe,fd' -i - -map '0:0' '-c:0' copy '-disposition:0' default -map '0:1' '-c:1' copy '-disposition:1' default -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale 90000 -f mp4 -y $FILE_PREFIX-p$3.mp4

  log "#Finish: merge_nokey_before_with_key encoded+coped p$3"
}

# loss_less_process $start $end
function loss_less_process() {
  grep_for_key_and_before $1
  #echo -e "$K_FRAME(key_frame) / $BEF_KEY_FRAME(before_key_frame)"

  # handle key frame
  cut_after $K_FRAME $2

  # handle no-key frame
  if [ "-1" = "$BEF_KEY_FRAME" ]; then
    log "No need to cut p${idx}'s frame before keyframe, \
    mark as total segment, from $1[$K_FRAME](s)-$2(s)."
    # rename single segment
    mv $FILE_PREFIX-smartcut-segment-copyed-tmp.mp4 $FILE_PREFIX-p${idx}.mp4
    return 0
  fi

  cut_before $1 $BEF_KEY_FRAME

  #log "About to merge $FILE_PREFIX-smartcut-segment-encoded-tmp.mp4 + $FILE_PREFIX-smartcut-segment-copyed-tmp.mp4 ==> $FILE_PREFIX-p${idx}_tmp.mp4"

  # merge
  merge_nokey_before_with_key $FILE_PREFIX-smartcut-segment-encoded-tmp $FILE_PREFIX-smartcut-segment-copyed-tmp $idx

  # remove temp
  rm $FILE_PREFIX*-smartcut-*tmp.mp4
}

log "Call job with multiple segment index: [${m}], origin video: ${o}."
log "#############################"

# 切分片段
# 00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33
seg=$(echo $m | tr "+" "\n")
#seg=$(echo $m | sed 's/+/\n/g')

idx=0
total_ts=0
for cp in $seg; do
  #echo ">outside [$cp]"
  let idx+=1
  eles=($(echo $cp | tr ',' "\n"))
  # 计算时间戳相差的秒数
  #start=$(date +%s -d ${eles[0]})
  start=$(echo ${eles[0]} | awk -F: '{ print ($1 * 3600) + ($2 * 60) + $3 }')
  #end=$(date +%s -d ${eles[1]})
  end=$(echo ${eles[1]} | awk -F: '{ print ($1 * 3600) + ($2 * 60) + $3 }')
  diff=$((end - start))
  log "====== #${idx} Cut for ${o} from ${eles[0]} to ${eles[1]},\
      idx: #$idx, duration: $(($diff / 60))min$(($total_ts % 60))s."
  total_ts=$((total_ts + diff))

  #lossless logic / params: src, from, to, idx
  loss_less_process $start $end
  log "\n============================="    
done


# ======================子项合并==========================
log "=============Merge for partitions==============="

# 将秒数转换为分钟和秒钟
minutes=$(($total_ts / 60))
seconds=$(($total_ts % 60))

log "###### Grep finished with ${o}, total duration:${total_ts}(s) = ${minutes}min${seconds}s . \n"

function compress() {

  # debug point
  #echo "debug point, exit!"
  #exit -1

  log "Ready to compress video: $1"
  src_size_info=$(get_file_size $1)
  # ffmpeg -i ${o}-with_total_${idx}_tocut.mp4 -vf scale=1920:1080 -preset fast -maxrate 8000k -bufsize 1.6M -c:a copy ${o}-with_total_${idx}_zipped.mp4
  ffmpeg -i $1 -preset veryfast -maxrate 8000k -bufsize 1.6M -c:a copy ${o}-with_total_${idx}_zipped.mp4
  size_info=$(get_file_size ${o}-with_total_${idx}_zipped.mp4)
  log "###### Done for compressing ${o}, Src-${src_size_info} / Zipped-${size_info}.\n"
}

if [ $idx -lt 2 ]; then
  log "#Skip merging with single seg, exit.\n"
  # rename
  mv ${o}-p${idx}.mp4 ${o}-with_single_tocut.mp4
  # compress
  compress ${o}-with_single_tocut.mp4
  rm ${o}-with_single_tocut.mp4
  exit 0
fi

# 批量合并
#(for i in $(seq 1 ${idx}); do echo "file file:'${o}-grep-${i}.mp4'"; done) | ffmpeg -protocol_whitelist file,pipe -f concat -safe 0 -i pipe: -vcodec copy -acodec copy ${o}-with_total_${idx}_tocut.mp4
(for i in $(seq 1 ${idx}); do echo "file file:'${o}-p${i}.mp4'"; done) | ffmpeg -protocol_whitelist file,pipe -f concat -safe 0 -i pipe: -c copy ${o}-with_total_${idx}_tocut.mp4

log "###### Done merge for ${o}, total segment count: ${idx}, total ts:${total_ts} = ${minutes}min${seconds}s . \n"

# 归档临时文件
rm -f ${o}-p*.mp4
#mkdir -p seg_list_${o}
#mv ${o}-p*.mp4 seg_list_${o}

# 压缩视频
compress ${o}-with_total_${idx}_tocut.mp4

# 删除剪切中间结果
rm ${o}-with_total_${idx}_tocut.mp4
