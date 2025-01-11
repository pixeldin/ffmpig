@echo off
chcp 65001

tasklist /fi "imagename eq nginx.exe" | findstr /i "nginx.exe" > NUL
if %errorlevel% equ 0 (
    REM 如果 nginx 进程存在，执行 taskkill
    echo "Nginx 进程存在，正在终止..."
    taskkill /f /t /im nginx*
)

echo "启动chfs..."
start "" /B chfsgui.exe

echo "启动Nginx..."
cd /d "E:\Developer\nginx\nginx-1.22.1"
start "" nginx.exe -c "E:\Developer\nginx\nginx-1.22.1\conf\nginx_chfs.conf"

:loop
    rem echo "running analyze.py"
    python.exe "E:\Developer\pix-ffmpig\py\analyze\analyze.py" "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log"
    
    REM 等待 60 秒
    timeout /t 60 /nobreak >nul
    
    REM 返回循环开始
    goto loop

pause