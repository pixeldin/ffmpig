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

REM 打印启动时间
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
    set "hour=%%a"
    set "minute=%%b"
    set "second=%%c"
)
set "hour=%hour: =0%"
echo ========= 程序启动时间: %hour%:%minute%:%second% =========

rem 更新60次(120秒 * 60 =2小时)后退出
set "counter=60"
:loop
    if %counter% LEQ 0 goto endloop
    echo --------- Update into summary ---------
    REM 提取目标日志
    type "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log" | findstr "vvv=1" > "E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log"

    REM 运行 analyze.py
    python.exe "E:\Developer\pix-ffmpig\py\analyze\analyze.py" "E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log"
    
    set /a counter-=1
    rem 每120秒执行一次刷新
    timeout /t 120 /nobreak >nul
    goto loop
:endloop

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