#!/bin/bash
#set -x

usage() {
    echo "Usage: $0 [-o 文件名前缀] [-m 切割片段, 如'00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33'] [-z 是否压缩(-1否, 默认是)] [-s 指定分辨率(默认2048:1080)]" 1>&2
  exit 1
}

while getopts ":o:m:z:s:" args; do
  case "${args}" in
  o)
    o=${OPTARG}
    ;;
  m)
    m=${OPTARG}
    ;;
  z)
    z=${OPTARG}
    ;;
  s)
    s=${OPTARG}
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
# 默认需要压缩
if [ "$z" != "-1" ]; then
  z="yes"
fi
# 默认需要压缩
if [ "$s" = "" ]; then
  s="2048:1080"
fi

FILE_PREFIX=${o}

######################## PixelLog ########################
function log() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  echo -e "${timestamp} ${input_string}" | tee -a ${o}_cut.log
}
function Dlog() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  #echo -e "${timestamp} ${input_string}" | tee -a ${o}_cut.log
  echo -e "\e[7;49;36m[D]\e[0m \033[36m${input_string} $2\033[0m" | tee >(sed "s/\x1B\[[0-9;]*[mGK]//g; s/^/$timestamp /" >> ${o}_cut.log)
}
function Ilog() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  #echo -e "${timestamp} ${input_string}" | tee -a ${o}_cut.log
  echo -e "\e[7;49;32m[I]\e[0m \033[32m${input_string} $2\033[0m" | tee >(sed "s/\x1B\[[0-9;]*[mGK]//g; s/^/$timestamp /" >> ${o}_cut.log)
}
function Wlog() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  #echo -e "${timestamp} ${input_string}" | tee -a ${o}_cut.log
  echo -e "\e[7;49;93m[W]\e[0m \033[33m${input_string} $2\033[0m" | tee >(sed "s/\x1B\[[0-9;]*[mGK]//g; s/^/$timestamp /" >> ${o}_cut.log)
}
function Elog() {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  #echo -e "${timestamp} ${input_string}" | tee -a ${o}_cut.log
  echo -e "\e[7;49;91m[E]\e[0m \033[31m${input_string} $2\033[0m" | tee >(sed "s/\x1B\[[0-9;]*[mGK]//g; s/^/$timestamp /" >> ${o}_cut.log)
}
######################## PixelLog ########################

function break_for_debug() {
  # debug point
  Dlog "For debug point"
  Dlog "================ Val: $1"
  Dlog "For debug point, exit"
  exit 0
}

# 获取视频信息: $1 (option:time_base/bit_rate/codec_name)
function get_metric_of() {
  echo $(ffprobe -v error -select_streams v:0 -show_entries stream=$1 -of default=noprint_wrappers=1:nokey=1 ${FILE_PREFIX}.mp4)
}

# 视频总帧数
TR=$(get_metric_of bit_rate)
# 视频时间基准
TB=$(get_metric_of time_base)
TB="${TB#*/}"
# 视频帧率
RFR=$(get_metric_of r_frame_rate)
# 视频编码格式
CodName=$(get_metric_of codec_name)

function get_file_size() {
  if [ -f "$1" ]; then
    local size=$(du -h "$1" | cut -f 1)
    echo "Size: $size"
  else
    echo "no param for get_file_size()."
  fi
}

# grep_for_key_and_before $timestamps
function grep_for_key_and_before() {
  local start=$1
  local end=$(expr "$start" + 5)
  Dlog "Grep pts, from $start(s) to $end(s)"
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

  # 当前秒关键帧的前一帧不存在同一秒或者'帧片段较短',则忽略
  if [ -z "$BEF_KEY_FRAME" ] || [ $(echo "$BEF_KEY_FRAME <= $start" | bc) -eq 1 ] || \
[ $(echo "$BEF_KEY_FRAME-$start <= 0.03" | bc) -eq 1 ]; then
    Wlog "Second time at $start(s), $BEF_KEY_FRAME(BEF_KEY_FRAME),\
ignore before key frame, reset as -1"
    BEF_KEY_FRAME="-1"
  fi

  Dlog "Grep $1(s) nearby result: $K_FRAME(K_FRAME) / $BEF_KEY_FRAME(BEF_KEY_FRAME)"
}

# cut from src $K_FRAME $end
function cut_after() {
  local duration=$(echo "scale=5; ${2}-${1}" | bc | sed 's/^\./0./')  
  #echo "After cut duration: $duration, prefix: $FILE_PREFIX"
  ffmpeg -hide_banner -ss $1 -i $FILE_PREFIX.mp4 -t $duration -map '0:0' '-c:0' copy -map '0:1' '-c:1' copy -map_metadata 0 -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale $TB -f mp4 -y $FILE_PREFIX-smartcut-segment-copyed-tmp.mp4
}

# cut from src $start $BEF_KEY_FRAME
function cut_before() {
  local duration=$(echo "scale=5; ${2}-${1}" | bc | sed 's/^\./0./')  
  #echo "After cut duration: $duration, prefix: $FILE_PREFIX, TR: $TR"
  ffmpeg -hide_banner -ss $1 -i ${FILE_PREFIX}.mp4 -ss 0 -t $duration -map '0:0' '-c:0' $CodName '-b:0' $TR -map '0:1' '-c:1' copy -ignore_unknown -video_track_timescale $TB -f mp4 -y $FILE_PREFIX-smartcut-segment-encoded-tmp.mp4
}

# 合并非关键帧(前)与关键帧时段(后) $encoded $coped $idx
function merge_nokey_before_with_key() {  
  echo -e "file 'file:${1}.mp4'\nfile 'file:${2}.mp4'" | ffmpeg -hide_banner -f concat -safe 0 -protocol_whitelist 'file,pipe,fd' -i - -map '0:0' '-c:0' copy '-disposition:0' default -map '0:1' '-c:1' copy '-disposition:1' default -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale $TB -f mp4 -y $FILE_PREFIX-p$3.mp4

  Dlog "#Finish: merge_nokey_before_with_key encoded+coped p$3"
}

# loss_less_process $start $end
function loss_less_process() {
  grep_for_key_and_before $1
  #echo -e "$K_FRAME(key_frame) / $BEF_KEY_FRAME(before_key_frame)"

  # handle key frame
  cut_after $K_FRAME $2

  # handle no-key frame
  if [ "-1" = "$BEF_KEY_FRAME" ]; then
    Wlog "No need to cut p${idx}'s frame before keyframe, \
mark as total segment, from $K_FRAME($1)-$2(s)."
    # rename as single segment
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

Ilog "Call job with multiple segment index: [${m}], origin video: ${o}, state about to zip? ${z}!"
Wlog "#############################"

# 切分片段
# 00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33
seg=$(echo $m | tr "+" "\n")

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
  Dlog "====== #${idx} Cut for ${o} from ${eles[0]} to ${eles[1]},\
 idx: #$idx, duration: $(($diff / 60))min$(($diff % 60))s."
  total_ts=$((total_ts + diff))

  #lossless logic / params: src, from, to, idx
  loss_less_process $start $end
  Wlog "============================="    
done


# ======================子项合并==========================
Ilog "=============Merge for partitions==============="

# 将秒数转换为分钟和秒钟
minutes=$(($total_ts / 60))
seconds=$(($total_ts % 60))

Ilog "###### Grep finished with ${o}, total duration:${total_ts}(s) = ${minutes}min${seconds}s . \n"

function compress() {
  Ilog "###### Ready to compress video: $1"
  src_size_info=$(get_file_size $1)

  # -preset [fast/faster/veryfast/superfast/ultrafast] 默认medium,
  # 画质逐级降低,压缩比逐级下降 
  #ffmpeg -i $1 -preset fast -vf scale=2048:1080 -maxrate 8000k -bufsize 1.6M -c:a copy cup-${o}-${idx}_zipped.mp4
  ffmpeg -i $1 -preset faster -vf scale=$s -b:v 8000k -maxrate 9000k -r $RFR -video_track_timescale $TB -bufsize 2M -c:a copy cup-${o}-${idx}_zipped.mp4

  size_info=$(get_file_size cup-${o}-${idx}_zipped.mp4)
  Ilog "###### Done compressing ${o}, Src-${src_size_info} / Zipped-${size_info}, duration: ${minutes}min${seconds}s.\n"
}

if [ $idx -lt 2 ]; then
  Dlog "#Skip merging with single seg, check the compress's necessary."
  single_ret="${o}-single_tozip"
  if [ "$z" = "-1" ]; then
    Wlog "------- With one segment, no need to compress.-------"
    single_ret="cup-${o}-${idx}_nozip.mp4"
    # rename and exit.
    mv ${o}-p${idx}.mp4 $single_ret.mp4
    exit 0
  fi
  
  # compress
  Ilog "------- With single seg, be ready to compress.-------"
  # rename and zip
  mv ${o}-p${idx}.mp4 $single_ret.mp4
  compress $single_ret.mp4
  rm $single_ret.mp4
  exit 0
fi

# 批量合并
ret="cup-${o}-${idx}_tozip.mp4"

if [ "$z" = "-1" ]; then
  ret="cup-${o}-${idx}_nozip.mp4"
fi

#(for i in $(seq 1 ${idx}); do echo "file file:'${o}-p${i}.mp4'"; done) | ffmpeg -protocol_whitelist file,pipe,fd -f concat -safe 0 -i pipe: -c copy $ret
(for i in $(seq 1 ${idx}); do echo "file file:'${o}-p${i}.mp4'"; done) | ffmpeg -hide_banner -f concat -safe 0 -protocol_whitelist 'file,pipe,fd' -i - -map '0:0' '-c:0' copy '-disposition:0' default -map '0:1' '-c:1' copy '-disposition:1' default -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -f mp4 -y $ret

Ilog "###### Done merge for ${o}, total segment count: ${idx}, total ts:${total_ts} = ${minutes}min${seconds}s . \n"

# 归档临时文件
rm -f ${o}-p*.mp4
#mkdir -p seg_list_${o}
#mv ${o}-p*.mp4 seg_list_${o}

# 压缩视频
if [ "$z" = "-1" ]; then
  Ilog "${o} no need to compress, done!"
  exit 0
fi

compress cup-${o}-${idx}_tozip.mp4
# 删除剪切中间结果
rm cup-${o}-${idx}_tozip.mp4
