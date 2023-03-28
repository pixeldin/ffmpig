#!/bin/bash
#set -x

usage() { echo "Usage: $0 [-m 切割片段, 如'00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33']" 1>&2; exit 1; }

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

if [ -z "${m}" ] ; then
    usage
    exit -1
fi

echo "Debug #Job with multiple segment index: [${m}]" 

seg=$(echo $m | tr "+" "\n")

idx=0
for cp in $seg
do
    #echo ">outside [$cp]"
    let idx+=1
    eles=($(echo $cp | tr ',' "\n"))

    # 计算时间戳相差的秒数
    start=$(date +%s -d ${eles[0]})
    end=$(date +%s -d ${eles[1]})
    diff=$((end-start))
    echo "====== Cut for ${o} from ${eles[0]} to ${eles[1]}_${idx}, diff: ${diff}"
    if [ ${diff} -le 45 ] ; then
      echo "====== 精确切割."
    else
      echo "====== 模糊切割."
    fi    

    #echo "ffmpeg -ss ${eles[0]} -to ${eles[1]} -i ${o}.mp4 -c copy ${o}-grep-${idx}.mp4"
done


# loging func
function log {
  local input_string="$1"
  local timestamp="$(date +'%Y-%m-%d %H:%M:%S.%3N')"
  echo "${timestamp} ${input_string}"
}

echo $(log "hello") >> test.log
sleep 1s
echo $(log "hello again 1s") >> test.log
