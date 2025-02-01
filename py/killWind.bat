@echo off
chcp 65001

rem 检查 chfsgui.exe 进程是否存在
tasklist /fi "imagename eq chfsgui.exe" | findstr /i "chfsgui.exe" > nul
if %errorlevel% equ 0 (
    echo "=== chfsgui.exe 进程存在，正在终止..."
    taskkill /f /t /im chfsgui.exe
) else (
    echo "=== 未找到 chfsgui.exe 进程。"
)

echo "-----------------------------"

rem 检查 chfs.exe 进程是否存在
tasklist /fi "imagename eq chfs.exe" | findstr /i "chfs.exe" > nul
if %errorlevel% equ 0 (
    echo "=== chfs.exe 进程存在，正在终止..."
    taskkill /f /t /im chfs.exe
) else (
    echo "=== 未找到 chfs.exe 进程。"
)

echo "-----------------------------"

tasklist /fi "imagename eq nginx.exe" | findstr /i "nginx.exe" > nul
if %errorlevel% equ 0 (
    echo "=== Nginx 进程存在，正在终止..."
    taskkill /f /t /im nginx*    
) else (
		echo "=== 未找到Nginx进程。"
)

echo "-----------------------------"

rem 检查 窗口名包括'windflow'的cmd进程是否存在
tasklist /fi "WindowTitle eq windflow*" | findstr /i "cmd.exe" > nul
if %errorlevel% equ 0 (
    echo "=== windflow cmd存在，正在终止..."
    taskkill /fi "WindowTitle eq windflow*"    
) else (
	echo "=== 未找到windflow cmd进程。"
)

pause
