@echo off
chcp 65001

REM 检查并终止 nginx 进程
tasklist /fi "imagename eq nginx.exe" | findstr /i "nginx.exe" > NUL
if %errorlevel% equ 0 (
    echo Nginx 进程存在，正在终止...
    taskkill /f /t /im nginx*
)

echo 启动chfs...
start "" /B chfsgui.exe

echo 启动Nginx...
cd /d "E:\Developer\nginx\nginx-1.22.1"
start "" nginx.exe -c "E:\Developer\nginx\nginx-1.22.1\conf\nginx_chfs.conf"

REM =========首次更新 提取日志=========
type "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log" | findstr "vvv=1" > "E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log"

REM 运行 analyze.py
python.exe "E:\Developer\pix-ffmpig\py\analyze\analyze.py" "E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log"
REM =========首次更新 提取日志=========

REM 打印启动时间
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
    set "hour=%%a"
    set "minute=%%b"
    set "second=%%c"
)
set "hour=%hour: =0%"
echo ========= 程序启动时间: %hour%:%minute%:%second% =========

REM 设置循环持续时间（2小时 = 7200 秒）
set /a "max_duration=7200"

REM 提取并规范化开始时间
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
    set "hour=%%a"
    set "minute=%%b"
    set "second=%%c"
)

REM 去除小时中的前导空格并补齐为两位数
set "hour=%hour: =0%"
if "%hour:~0,1%"=="0" set "hour=%hour:~1%"

REM 计算开始时间（秒）
set /a "start_time=hour*3600 + minute*60 + second"

:loop
    REM 子循环检查时间
    set /a "wait_count=0"
    :wait_loop
        REM 提取并规范化当前时间
        for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
            set "hour=%%a"
            set "minute=%%b"
            set "second=%%c"
        )

        REM 去除小时中的前导空格并补齐为两位数
        set "hour=%hour: =0%"
        if "%hour:~0,1%"=="0" set "hour=%hour:~1%"

        REM 计算当前时间（秒）
        set /a "current_time=hour*3600 + minute*60 + second"
        
        REM 计算已经过去的时间
        set /a "elapsed_time=current_time - start_time"
        
        REM 处理跨天情况（如果时间超过24小时）
        if %elapsed_time% lss 0 set /a "elapsed_time+=86400"
        
        REM 检查是否超过 max_duration 秒
        if %elapsed_time% geq %max_duration% (
            echo 运行周期结束，退出循环...
            goto :end
        )

        REM 增加等待计数器（每秒检查）
        set /a "wait_count+=1"
        REM 如果等待时间达到 120 秒，执行日志处理
        if !wait_count! geq 120 (
            goto :process_log
        )

        REM 等待 1 秒
        timeout /t 1 /nobreak >nul
        goto :wait_loop

    :process_log
    REM 提取目标日志
    type "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log" | findstr "vvv=1" > "E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log"

    REM 运行 analyze.py
    python.exe "E:\Developer\pix-ffmpig\py\analyze\analyze.py" "E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log"
    
    REM 返回主循环
    goto :loop

:end
echo 脚本执行完毕, 执行Clean。

REM 清除操作（保持原样）
tasklist /fi "imagename eq chfsgui.exe" | findstr /i "chfsgui.exe" > nul
if %errorlevel% equ 0 (
    echo === chfsgui.exe 进程存在，正在终止...
    taskkill /f /t /im chfsgui.exe
) else (
    echo === 未找到 chfsgui.exe 进程。
)

echo -----------------------------

tasklist /fi "imagename eq chfs.exe" | findstr /i "chfs.exe" > nul
if %errorlevel% equ 0 (
    echo === chfs.exe 进程存在，正在终止...
    taskkill /f /t /im chfs.exe
) else (
    echo === 未找到 chfs.exe 进程。
)

echo -----------------------------

tasklist /fi "imagename eq nginx.exe" | findstr /i "nginx.exe" > nul
if %errorlevel% equ 0 (
    echo === Nginx 进程存在，正在终止...
    taskkill /f /t /im nginx*
) else (
    echo === 未找到Nginx进程。
)

echo -----------------------------

echo === 准备删除 Temp 下的 chfs相关文件...
del /q "C:\Users\Pixel_Pig\AppData\Local\Temp\chfs_*.jpg" 2>nul
del /q "C:\Users\Pixel_Pig\AppData\Local\Temp\chfs.exe" 2>nul
echo === 删除操作完成。

REM 打印结束时间
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
    set "hour=%%a"
    set "minute=%%b"
    set "second=%%c"
)
set "hour=%hour: =0%"
echo ========= 程序结束时间: %hour%:%minute%:%second% =========

pause