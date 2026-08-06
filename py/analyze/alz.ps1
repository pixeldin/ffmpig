$ErrorActionPreference = "Stop"

$NginxHome = "E:\Developer\nginx\nginx-1.22.1"
$NginxConf = "E:\Developer\nginx\nginx-1.22.1\conf\nginx_chfs.conf"
$AccessLogFile = "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log"
$ProjectHome = "E:\Developer\pix-ffmpig"
$VisitDb = "E:\Developer\pix-ffmpig\py\analyze\visit_stats.db"
$ChfsRoot = "I:\files"
$Counter = 60
$IntervalSeconds = 120

function Write-RunTime {
    param([string]$Label)
    Write-Host ("========= {0}: {1} =========" -f $Label, (Get-Date -Format "HH:mm:ss"))
}

function Stop-ProcessIfExists {
    param(
        [string]$Name,
        [string]$Label
    )

    $processes = Get-Process -Name $Name -ErrorAction SilentlyContinue
    if ($processes) {
        Write-Host "正在终止 $Label..."
        $processes | Stop-Process -Force
    } else {
        Write-Host "未找到 $Label 进程。"
    }
}

function Test-RequiredPath {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "未找到${Label}: $Path"
    }
}

function Invoke-Step {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$ErrorMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$ErrorMessage, exit code: $LASTEXITCODE"
    }
}

try {
    Write-Host "========================================"
    Write-Host "CHFS 文件访问日志分析工具"
    Write-Host "========================================"
    Write-Host "Nginx目录: $NginxHome"
    Write-Host "Nginx配置: $NginxConf"
    Write-Host "访问日志: $AccessLogFile"
    Write-Host "SQLite数据库: $VisitDb"
    Write-Host "CHFS根目录: $ChfsRoot"
    Write-Host "CHFS访问地址: 自动检测本机局域网IP"
    Write-Host ""

    Test-RequiredPath "$ProjectHome\py\analyze\ingest_log.py" "ingest_log.py"
    Test-RequiredPath "$ProjectHome\py\analyze\report_builder.py" "report_builder.py"
    Test-RequiredPath $NginxHome "Nginx目录"
    Test-RequiredPath $NginxConf "Nginx配置"
    Test-RequiredPath $AccessLogFile "访问日志"

    if (-not (Test-Path -LiteralPath $ChfsRoot)) {
        Write-Host "警告: 未找到 CHFS 根目录: $ChfsRoot"
        Write-Host "将跳过文件系统扫描结果，仅基于数据库访问记录生成报表。"
        Write-Host "如果需要显示文件存在状态、文件大小和预览图，请确认 I: 盘已挂载。"
        Write-Host ""
    }

    $existingNginx = Get-Process -Name "nginx" -ErrorAction SilentlyContinue
    if ($existingNginx) {
        Write-Host "Nginx 进程存在，正在终止..."
        $existingNginx | Stop-Process -Force
    }

    Write-Host "启动 chfsgui..."
    Start-Process -FilePath "chfsgui.exe" -WindowStyle Hidden

    Write-Host "启动 Nginx..."
    Start-Process -FilePath "$NginxHome\nginx.exe" -ArgumentList @("-c", $NginxConf) -WorkingDirectory $NginxHome -WindowStyle Hidden

    Write-RunTime "程序启动时间"

    while ($Counter -gt 0) {
        Write-Host ""
        Write-Host "--------- 更新访问统计 ---------"

        Invoke-Step "python.exe" @(
            "$ProjectHome\py\analyze\ingest_log.py",
            "tail",
            $AccessLogFile,
            $VisitDb
        ) "增量同步失败"

        Invoke-Step "python.exe" @(
            "$ProjectHome\py\analyze\report_builder.py",
            $VisitDb,
            $ChfsRoot
        ) "报表生成失败"

        Write-RunTime "更新日志时间"
        $Counter -= 1
        Start-Sleep -Seconds $IntervalSeconds
    }
}
catch {
    Write-Host "错误: $($_.Exception.Message)"
    exit 1
}
finally {
    Write-Host ""
    Write-Host "脚本执行完毕，开始清理。"

    Stop-ProcessIfExists "chfsgui" "chfsgui.exe"
    Stop-ProcessIfExists "nginx" "Nginx"

    Write-Host "准备删除 Temp 下的 chfs 相关文件..."
    Remove-Item -LiteralPath "C:\Users\Pixel_Pig\AppData\Local\Temp\chfs.exe" -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\Users\Pixel_Pig\AppData\Local\Temp\chfs_*.jpg" -Force -ErrorAction SilentlyContinue
    Write-Host "删除操作完成。"

    Write-RunTime "程序结束时间"
}
