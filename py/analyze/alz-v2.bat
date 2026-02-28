@echo off
chcp 65001 >nul
echo ========================================
echo 文件访问日志分析工具 (增强版 v2)
echo ========================================
echo.

REM 配置参数
set LOG_FILE=E:\Developer\nginx\nginx-1.22.1\logs\tar_chfs.log
set CHFS_ROOT=I:\files
set CHFS_URL=http://192.168.28.67:9527

echo 日志文件: %LOG_FILE%
echo CHFS 根目录: %CHFS_ROOT%
echo CHFS URL: %CHFS_URL%
echo.
echo 开始分析...
echo.

python analyze-v2.py "%LOG_FILE%" "%CHFS_ROOT%" "%CHFS_URL%"

echo.
echo 按任意键退出...
pause >nul
