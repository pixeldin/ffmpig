#!/bin/bash

# 检查输入参数
if [ $# -ne 1 ]; then
  echo "Usage: $0 <log_file_path>"
  exit 1
fi

# 日志文件路径
log_file=$1

# 全局 map，用于存储每个 mp3 文件及其访问记录
declare -A mp3_access_map

# 辅助函数：将日期时间字符串转为时间戳
convert_to_timestamp() {
  # 输入时间格式：2025-01-08T11:23:19+08:00
  input_time="$1"

  # 去掉时区部分（例如 +08:00）并替换 "T" 为 " "，将格式改为 "2025-01-08 11:23:19"
  cleaned_time=$(echo "$input_time" | sed 's/[+,-][0-9][0-9]:[0-9][0-9]//g' | sed 's/T/ /')

  # 转换为 Unix 时间戳
  timestamp=$(date -d "$cleaned_time" +%s 2>/dev/null)

  # 如果转换失败，则输出错误信息
  if [ -z "$timestamp" ]; then
    echo "Error: Failed to convert date '$input_time'"
    return 1
  fi

  # 返回转换后的时间戳
  echo "$timestamp"
}

# 遍历日志文件
while IFS= read -r line; do
  # 提取访问时间和路径
  access_time=$(echo "$line" | awk '{print $1}' | sed 's/\[//g' | sed 's/\]//g')  # 格式：[2025-01-08T11:23:18+08:00]
  mp3_path=$(echo "$line" | awk '{print $3}' | sed 's/\"//g' | sed 's/\?.*//')  # 提取路径
  # echo "$timestamp === $access_time ++++ $mp3_path"
  # 提取时间戳
  timestamp=$(convert_to_timestamp "$access_time")
  
  # 如果时间转换失败，跳过当前行
  if [ $? -ne 0 ]; then
    continue
  fi

  # 提取文件名（例如 apple-v1587.mp3）
  mp3_filename=$(basename "$mp3_path")  

  # 提取文件所在的前两级目录
  mp3_dir=$(dirname "$mp3_path")
  first_level_dir=$(echo "$mp3_dir" | awk -F'/' '{print $(NF-1)}')  # 第一层目录
  second_level_dir=$(echo "$mp3_dir" | awk -F'/' '{print $(NF-2)}')  # 第二层目录

  # 拼接前两级目录
  file_path="${second_level_dir}/${first_level_dir}"
  # echo "*********** $file_path"
  # 生成 key，作为存储访问记录的标识
  key="${file_path}/${mp3_filename}"

  # echo "$timestamp === $mp3_filename ++++ $key"

  # 如果该文件之前访问过，检查时间差是否大于2分钟
  if [[ -n "${mp3_access_map[$key]}" ]]; then
    last_access_time="${mp3_access_map[$key]##*,}"
    last_access_timestamp=$(convert_to_timestamp "$last_access_time")

    # 判断访问时间差是否大于2分钟
    if (( timestamp - last_access_timestamp > 120 )); then
      # echo "timestamp - last_access_timestamp > 120 for $key"
      mp3_access_map["$key"]="${mp3_access_map[$key]},$access_time"
    fi
  else
    # 如果是第一次访问，初始化记录
    # echo "init for $key, at $access_time"
    mp3_access_map["$key"]="$access_time"
  fi

done < "$log_file"

# 统计并排序访问频次
declare -A frequency_map

# 计算每个文件的访问次数
for key in "${!mp3_access_map[@]}"; do
  times=(${mp3_access_map[$key]//,/ })  # 按逗号分割时间
  count=${#times[@]}
  
  # 提取路径部分（避免路径重复）
  file_path_and_name=$(echo "$key" | sed 's/\/[^/]*$//')  # 只保留最后一级目录之前的部分
  
  # 输出文件路径及名称
  # echo "file_path_and_name === $key + $file_path_and_name"
  
  # 将访问次数及文件路径信息存入频次统计
  frequency_map["$key"]="$count ${times[*]}"
done

# Debug 遍历并打印 frequency_map 中的键值对
#for key in "${!frequency_map[@]}"; do
#    echo "Key: $key, Value: ${frequency_map[$key]}"
#done

for key in "${!frequency_map[@]}"; do
    # 输出键和对应的值（包括频次和时间戳）
    echo -e "$key\t${frequency_map[$key]}"
done | sort -t$'\t' -k2,2nr  # 根据（频次）倒序

