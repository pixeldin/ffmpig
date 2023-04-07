#!/bin/bash

function cover_win_path_to_unix() {
  if [[ $1 == [A-Za-z]:\\* ]]; then
    # 处理win路径格式
    linux_path=$(echo $1 | sed 's/\\/\//g')
    # 获取第一个字符，即盘符
    drive=${linux_path:0:1}
    # 将盘符替换为小写字母，并在路径前面加上 `/`
    linux_path="/${drive,,}${linux_path:2}"
    echo "$linux_path"
  else
    echo "no wind path, keep it origin: "$1
  fi
}

cv_path=$(cover_win_path_to_unix $1)
echo "$cv_path"
exit 0

spwd=$(pwd)
# job1
# target dir
cd "/f/tmp/"
echo -e "jump to $(pwd), filelist: \n$(ls)\n" | tee -a $spwd/batch.log

# job2
cd "/f/tmp/"
echo -e "jump to $(pwd), filelist: \n$(ls)\n" | tee -a $spwd/batch.log


wait
echo "job list finished."
