#!/bin/bash

usage() {
    echo "--------------------------------------------"
    echo "请输入正确的时间格式!" 
    echo "Usage: $0 [-o 文件名前缀] [-m 切割片段, 如'00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33'] " 1>&2
    echo "--------------------------------------------"
  exit 1
}

input="default.mp4"

while getopts ":o:m:z:s:" args; do
  case "${args}" in
  o)
    input=${OPTARG}
    ;;
  m)
    segs=${OPTARG}
    ;;
  *)
    usage
    ;;
  esac
done


if [ -z "${segs}" ]; then
  usage
  exit -1
fi

# Check for seg(-m 'args') format
pattern="^([0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{2}:[0-9]{2}:[0-9]{2})+(\+[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{2}:[0-9]{2}:[0-9]{2})*$"

if [[ $segs =~ $pattern ]]; then
    #echo "Segment's format checking pass, -m:[ ${segs} ]"
    :
else
    echo "Segments(-m args) format error: ${segs}"
    usage
    exit -1
fi

if [[ $input == *.* ]]; then
  # 带后缀则分解
  FILE_PREFIX="${input%.*}"
  FILE_SUFFIX="${input##*.}"
else
  FILE_PREFIX=${input}
  # 默认使用mp4后缀
  FILE_SUFFIX="mp4"
fi

FILE_NAME="${FILE_PREFIX}.${FILE_SUFFIX}"

# 切分片段
# 00:00:03,00:00:41+00:01:03,00:01:11+00:02:30,00:02:33
seg=$(echo $segs | tr "+" "\n")

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
  echo "====== #${idx} from ${eles[0]} to ${eles[1]},\
 idx: #$idx, duration: $(($diff / 60)) min $(($diff % 60)) s."
  total_ts=$((total_ts + diff))
done

# 将秒数转换为分钟和秒钟
minutes=$(($total_ts / 60))
seconds=$(($total_ts % 60))

echo "###### Grep finished with ${FILE_PREFIX}, total video duration:${total_ts}(s) = ${minutes} min ${seconds} s."
