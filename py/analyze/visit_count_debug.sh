#!/bin/bash

declare -A frequency_map

# 假设你的 frequency_map 已经定义并填充
frequency_map["Cow/dreamMilk/SISdk-09v3-S1.mp3"]="2 2025-01-08T11:25:35+08:00 2025-01-08T11:31:03+08:00"
frequency_map["cute/HFL-newWell/prSdk-06v3-s2.mp3"]="1 2025-01-08T11:30:28+08:00"
frequency_map["body/northFlower/siSdk-25v1-s1.mp3"]="1 2025-01-08T11:23:18+08:00"
frequency_map["body/wood-love/dsSdk-v1587.mp3"]="1 2025-01-08T11:23:18+08:00"
frequency_map["Cow/dreamMilk/SISdkv-142.mp3"]="1 2025-01-08T11:26:32+08:00"
frequency_map["wf/standflower/BIKMSdkv-006.mp3"]="1 2025-01-08T11:31:35+08:00"

# 用一个临时关联数组按目录层级组织内容
declare -A folder_structure

# 遍历 frequency_map，把文件按目录层级结构组织
for key in "${!frequency_map[@]}"; do
    # 提取目录部分和文件名
    folder=$(dirname "$key")
    filename=$(basename "$key")
    
    # 构建目录层次
    folder_structure["$folder"]+="$filename|${frequency_map[$key]}\n"
done

# 用递归函数按目录结构输出
print_structure() {
    local dir="$1"
    local indent="$2"

    # 打印当前目录的内容
    if [[ -n "${folder_structure[$dir]}" ]]; then
        # 目录层级输出
        echo -e "${indent}${dir%/*}:"
        
        # 获取当前目录下的文件
        local files=($(echo -e "${folder_structure[$dir]}" | sort -k1,1))
        
        for file_info in "${files[@]}"; do
            # 输出文件，进一步增加缩进
            filename=$(echo "$file_info" | cut -d'|' -f1)
            metadata=$(echo "$file_info" | cut -d'|' -f2-)
            echo -e "${indent}    - $filename $metadata"
        done
    fi

    # 递归遍历子目录
    for sub_dir in $(echo "${!folder_structure[@]}" | tr ' ' '\n' | grep "^$dir/"); do
        print_structure "$sub_dir" "$indent    "
    done
}

# 按根目录排序并打印
for root_dir in $(echo "${!folder_structure[@]}" | tr ' ' '\n' | sort); do
    print_structure "$root_dir" ""
done

