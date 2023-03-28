# to findout
#-c:v libx264 
ffmpeg -i dev-skill.mp4 -c:v libx264 -crf 23 -preset medium -maxrate 8000k -bufsize 1M -c:a copy Test.mp4

# -hwaccel cuvid -c:v h264_cuvid
ffmpeg -i dev-skill.mp4 -hwaccel cuvid -c:v h264_cuvid -crf 23 -preset medium -maxrate 8000k -bufsize 1M -c:a copy Test-accel.mp4
