#!/bin/bash

# 定义正则表达式进行匹配
pattern="^([0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{2}:[0-9]{2}:[0-9]{2})+(\+[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{2}:[0-9]{2}:[0-9]{2})*$"

# 检查seg变量是否符合格式要求
if [[ $1 =~ $pattern ]]; then
    echo "seg变量格式正确"
else
    echo "seg变量格式不符合要求"
fi
