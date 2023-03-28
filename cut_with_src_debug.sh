#!/bin/bash
#set -x

usage() { echo "Usage: $0 [-o 文件名前缀] [-m 切割片段, 如'00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33']" 1>&2; exit 1; }

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

if [ -z "${o}" ] || [ -z "${m}" ] ; then
    usage
    exit -1
fi

function log {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  echo -e "${timestamp} ${input_string}" >> ${o}_cut.log
}

function get_file_size() {
    if [ -f "$1" ]; then
        local size=$(du -h "$1" | cut -f 1)
        echo "大小: $size"
    else
        echo "file not exists."
    fi
}

function llprocess() {
    # handle key frame
    
    # handle no-key frame
    
    # merge
}

log "Pixel #Job with multiple segment index: [${m}], origin video: ${o}." 



# 切分片段
# 00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33
seg=$(echo $m | tr "+" "\n")
#seg=$(echo $m | sed 's/+/\n/g')

idx=0
total_ts=0
for cp in $seg
do
    #echo ">outside [$cp]"
    let idx+=1
    eles=($(echo $cp | tr ',' "\n"))
    # 计算时间戳相差的秒数
    start=$(date +%s -d ${eles[0]})
    end=$(date +%s -d ${eles[1]})
    diff=$((end-start))
    log "====== Cut for ${o} from ${eles[0]} to ${eles[1]}_${idx}, 时长: ${diff}(秒)."
    total_ts=$((total_ts+diff))

    #TODO Replace with lossless logic / params: src, from, to, idx
    #llprocess ${o}.mp4 ${eles[0]} ${eles[1]} ${idx}

    #ffmpeg -hide_banner -i ${o}.mp4 -ss ${eles[0]} -to ${eles[1]} -map '0:0' '-c:0' copy -map '0:1' '-c:1' copy -avoid_negative_ts 1 -copyts -start_at_zero -force_key_frames:v "expr:gte(t,n_forced/50)" -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale 90000 ${o}-grep-${idx}.mp4
    #ffmpeg -i ${o}.mp4 -ss ${eles[0]} -to ${eles[1]} -c copy ${o}-grep-${idx}.mp4
    sleep 1s 
done

# 将秒数转换为分钟和秒钟
minutes=$(( $total_ts / 60 ))
seconds=$(( $total_ts % 60 ))


log "###### Done for grep ${o}, 总时长:${total_ts}(秒) = ${minutes}分${seconds}秒 . \n"


function compress {

  # debug point
  #echo "debug point, exit!"
  #exit -1

  log "Ready to compress video: $1"
  src_size_info=$(get_file_size $1)
  # ffmpeg -i ${o}-with_total_${idx}_tocut.mp4 -vf scale=1920:1080 -preset fast -maxrate 8000k -bufsize 1.6M -c:a copy ${o}-with_total_${idx}_zipped.mp4
  ffmpeg -i $1 -preset fast -maxrate 8000k -bufsize 1.6M -c:a copy ${o}-with_total_${idx}_zipped.mp4
  size_info=$(get_file_size ${o}-with_total_${idx}_zipped.mp4)
  log "###### Done for compressing ${o}, Src-${src_size_info} / Zipped-${size_info}.\n"
}

if [ $idx -lt 2 ]; then
    log "#Skip merging with single seg, exit.\n"
    # rename
    mv ${o}-grep-${idx}.mp4 ${o}-with_single_tocut.mp4
    # compress
    compress ${o}-with_single_tocut.mp4
    exit 0
fi

# debug break 
log "break for debug"
exit 0

# 批量合并
#(for i in $(seq 1 ${idx}); do echo "file file:'${o}-grep-${i}.mp4'"; done) | ffmpeg -protocol_whitelist file,pipe -f concat -safe 0 -i pipe: -vcodec copy -acodec copy ${o}-with_total_${idx}_tocut.mp4
(for i in $(seq 1 ${idx}); do echo "file file:'${o}-grep-${i}.mp4'"; done) | ffmpeg -protocol_whitelist file,pipe -f concat -safe 0 -i pipe: -c copy ${o}-with_total_${idx}_tocut.mp4

log "###### Done cutting for ${o}, total segment count: ${idx}, total ts:${total_ts} = ${minutes}分${seconds}秒 . \n"

# 归档临时文件
rm -f ${o}-grep-*.mp4
#mkdir -p seg_list_${o}
#mv ${o}-grep-*.mp4 seg_list_${o}

# 压缩视频
compress ${o}-with_total_${idx}_tocut.mp4

#rm -f ${o}-with_total_${idx}_tocut.mp4
