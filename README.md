# ffmpeg 剪切片段逻辑
Grep From (`A.mp4`+`B.mp4`) ==> `C.mp4`
## For A (源文件)
- Grep
- cover
## For B (已加工) 
- Grep if necessary, then cover again
## Merge A+B to C

### Grep-1 [关键帧+目标时长后段]提取 (TA之后的关键帧-TB)
提取片段思路: From TA to TB  
1. 根据时间片分别将`$TB`,`$TB`转成秒数 `$AS`,`$BS`
2. 使用ffprobe导出关键帧, `ffprobe -v error -read_intervals '$AS%$BS' -show_packets -select_streams 0 -show_entries 'packet=pts_time,flags' -of csv 'B.mp4' > $AS_$BS_PTS_REC.csv`
3. 从`csv文件找出`$AS`时间点后面最近关键帧的位置`$K_AS`作为起点
4. 提取 (`$BS` - `$K_AS`)差值`MS`作为-t参数的时长, `ffmpeg -hide_banner -ss '$K_AS' -i 'input.mp4' -t '$MS' -map '0:0' '-c:0' copy -map '0:1' '-c:1' copy -map_metadata 0 -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale 90000 -f mp4 -y 'smartcut-segment-copy-0.mp4'`

### 查看总比特率
`$TR`=`ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 input.mp4`

### Grep-2 [目标时长前段+(非关键帧)最近点]提取 (TA-TA之后的非关键帧)
1. 从`csv文件找出`K_AS`关键帧点**前**最近的非关键帧`NK_BS`作为终点
2. 计算关键帧前补上时长: (`$NK_BS` - `$TA`)差值`$NK_S`
3. `ffmpeg -hide_banner -ss '$TA' -i 'input.mp4' -ss 0 -t '$NK_S' -map '0:0' '-c:0' h264 '-b:0' $TR -map '0:1' '-c:1' copy -ignore_unknown -video_track_timescale 90000 -f mp4 -y 'smartcut-segment-encode-0.mp4'`

### Merge 1-2
`echo -e "file 'file:smartcut-segment-encode-0.mp4'\nfile 'file:smartcut-segment-copy-0.mp4'" | ffmpeg -hide_banner -f concat -safe 0 -protocol_whitelist 'file,pipe' -i - -map '0:0' '-c:0' copy '-disposition:0' default -map '0:1' '-c:1' copy '-disposition:1' default -movflags '+faststart' -default_mode infer_no_subs -ignore_unknown -video_track_timescale 90000 -f mp4 -y 'output-$TA-$TB.mp4'`

## Reference
Thanks from LosslessCut :)
