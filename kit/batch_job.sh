#!/bin/bash

sTime=$(date +%s)
function PrintJobTime() {
  eTime=$(date +%s)
  pdiff=$((eTime - sTime))
  pmin=$((pdiff / 60))
  psec=$((pdiff % 60))
  phour=$((pmin / 60))
  pmin=$((pmin % 60))

  if [ $phour -eq 0 ]
  then
    echo -e "\n\e[31;40m#Batch-Job done, from $(date -d @$sTime +"%m-%d %H:%M:%S") to \
$(date -d @$eTime +"%H:%M:%S"), costs: ${pmin}min${psec}s\e[0m\n"
  else
    echo -e "\n\e[31;40m#Batch-Job done, from $(date -d @$sTime +"%m-%d %H:%M:%S") to \
$(date -d @$eTime +"%H:%M:%S"), costs: ${phour}h${pmin}min${psec}s\e[0m\n"
  fi

}


function cover_win_path() {
  if [[ $1 == [A-Za-z]:\\* ]]; then
    # 处理win路径格式
    linux_path=$(echo $1 | sed 's/\\/\//g')
    # 获取第一个字符，即盘符
    drive=${linux_path:0:1}
    # 将盘符替换为小写字母，并在路径前面加上 `/`
    linux_path="/${drive,,}${linux_path:2}"
    echo "$linux_path"
  else
    echo $1
  fi
}

#cv_path=$(cover_win_path $1)
#echo "$cv_path"

spwd=$(pwd)

function jump() {
  cv_path=$(cover_win_path "$1")
  cd "${cv_path}"
  # git-bash --cd="${cv_path}"
  start "" "git-bash.exe" --cd="${cv_path}"
  echo -e "$(date -d @$sTime +"%Y-%m-%d %H:%M:%S") from $spwd jump to $(pwd), filelist: \n$(ls)\n" | tee -a $spwd/batch.log
}

###################################################################################

# 执行单个 cut 任务
# 参数: $1=输出文件名, $2=时间范围, $3...$n=额外参数(如 -z -1)
function run_cut() {
  local output="$1"
  local time_range="$2"
  shift 2
  local extra_args="$@"
  
  if [ -n "$extra_args" ]; then
    cut_with_src.sh -o "$output" -m "$time_range" $extra_args
  else
    cut_with_src.sh -o "$output" -m "$time_range"
  fi
}

# 执行一个完整的 job（包含跳转目录和多个 cut 任务）
# 参数: $1=目录路径, $2...$n=cut任务参数（每3个参数为一组：输出文件,时间范围,额外参数）
function run_job() {
  local dir="$1"
  shift
  
  jump "$dir"
  
  # 处理所有 cut 任务
  while [ $# -gt 0 ]; do
    local output="$1"
    local time_range="$2"
    local extra_args="$3"
    shift 3
    
    run_cut "$output" "$time_range" $extra_args
  done
}

###################################################################################
# 任务配置区域 - 只需要修改这里的参数即可
# job1
# jump "D:\temp\snow"
# cut_with_src.sh -o to-cut.mp4 -m 00:00:01,00:00:05 -z -1
# cut_with_src.sh -o to-cut-2.mp4 -m 00:00:01,00:00:05

# job2
# jump "D:\temp\flower"
# cut_with_src.sh -o to-cut-v3.mp4 -m 00:00:02,00:00:08
###################################################################################

# job1: snow 目录，2个cut任务
run_job "D:\temp\snow" \
  "to-cut.mp4" "00:00:01,00:00:05" "-z -1" \
  "to-cut-2.mp4" "00:00:01,00:00:05" ""

# job2: flower 目录，1个cut任务
run_job "D:\temp\flower" \
  "to-cut-v2.mp4" "00:00:02,00:00:08" ""

# job3: 示例 - 多个cut任务，有的带额外参数有的不带
# run_job "D:\temp\example" \
#   "output1.mp4" "00:00:01,00:00:10" "-z -1" \
#   "output2.mp4" "00:00:05,00:00:15" "" \
#   "output3.mp4" "00:00:10,00:00:20" "-z -1"

##################################################################
wait
PrintJobTime
