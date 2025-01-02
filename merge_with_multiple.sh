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

# ----------------- v1 -----------------
#(for f in "${ARGS[@]}"; do echo "file file:'$f'"; done) | ffmpeg -protocol_whitelist file,pipe -f concat -safe 0 -i pipe: -vcodec copy -acodec copy $output
input_files=()

#echo "ffmpeg command to merge videos:"
#(for f in "${ARGS[@]}"; do echo "file '$f'"; done) | while read line; do
#    echo "$line"
#done
# ----------------- v1 -----------------

# ----------------- v2 -----------------
# 开启 nullglob，这样如果没有文件匹配，会返回一个空数组
shopt -s nullglob
for pattern in "${ARGS[@]}"; do
    # 使用 glob 扩展获取符合模式的文件
    matched_files=($pattern)

    # 如果没有匹配到任何文件，则输出提示并中断脚本
    if [ ${#matched_files[@]} -eq 0 ]; then
        echo "错误：没有匹配到文件：$pattern"
        exit 1
    fi

    # 将匹配到的文件加入数组
    input_files+=( "${matched_files[@]}" )
done
# ----------------- v2 -----------------

# 关闭 nullglob
shopt -u nullglob

(for f in "${input_files[@]}"; do echo "file file:'$f'"; done) | ffmpeg -protocol_whitelist file,pipe,fd -f concat -safe 0 -i pipe: -vcodec copy -acodec copy $output

#echo "ffmpeg command to merge into $output videos by:"
#(for f in "${input_files[@]}"; do echo "file '$f'"; done) | while read line; do
#    echo "$line"
#done

input_files=()

