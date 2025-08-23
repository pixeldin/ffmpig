@echo off
chcp 65001

:: 检查并终止 nginx 进程
echo 检查并终止 nginx 进程

:: 启动 chfs 和 Nginx
echo 启动chfs...
echo 启动Nginx...

:: 打印启动时间
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
    set "hour=%%a"
    set "minute=%%b"
    set "second=%%c"
)
set "hour=%hour: =0%"
echo ========= 程序启动时间: %hour%:%minute%:%second% =========

:: 提取日志并运行 analyze.py（每分钟一次，共三次）
echo ============= 开始执行日志提取和 analyze.py =============
set "counter=0"
:loop
    if %counter% GEQ 3 goto endloop
    echo 提取目标日志 和 运行 analyze.py

    set /a counter+=1
    timeout /t 3 /nobreak >nul
    goto loop
:endloop
echo ============= 日志提取和 analyze.py 执行完成 =============

:: 清理并结束
echo Ready to cleaning

:: 打印结束时间
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do (
    set "hour=%%a"
    set "minute=%%b"
    set "second=%%c"
)
set "hour=%hour: =0%"
echo "========= 程序结束时间: %hour%:%minute%:%second% ========="

pause