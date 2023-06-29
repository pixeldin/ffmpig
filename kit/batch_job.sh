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
  cv_path=$(cover_win_path $1)
  cd "${cv_path}"
  # git-bash --cd="${cv_path}"
  start "" "git-bash.exe" --cd="${cv_path}"
  echo -e "from $spwd jump to $(pwd), filelist: \n$(ls)\n" | tee -a $spwd/batch.log
}

###################################################################################

# job1
jump "D:\temp\snow"
cut_with_src.sh -o to-cut.mp4 -m 00:00:01,00:00:05 &

# job2
jump "D:\temp\flower"
cut_with_src.sh -o to-cut-v2.mp4 -m 00:00:02,00:00:08

###################################################################################
wait
PrintJobTime
