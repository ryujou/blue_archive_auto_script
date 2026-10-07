param(
    [string]$PythonPath = "$PSScriptRoot\.env\python.exe",
    [int]$DurationMinutes = 45,
    [string]$MuMuManagerPath,
    [int]$CloseWaitSeconds = 10
)

$ErrorActionPreference = "Stop"

function Resolve-MuMuManagerPath {
    param(
        [string]$CustomPath
    )

    if ($CustomPath) {
        if (-not (Test-Path -LiteralPath $CustomPath -PathType Leaf)) {
            throw "MuMuManager.exe not found at custom path: $CustomPath"
        }
        return $CustomPath
    }

    $cmd = Get-Command MuMuManager.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source -PathType Leaf)) {
        return $cmd.Source
    }

    $candidates = @(
        "D:\Program\MuMuPlayer-12.0\nx_main\MuMuManager.exe",
        "C:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe",
        "C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\MuMuManager.exe",
        "C:\Program Files\Netease\MuMuPlayer-12\shell\MuMuManager.exe",
        "C:\Program Files\Netease\MuMuPlayerGlobal-12\shell\MuMuManager.exe",
        "C:\Program Files (x86)\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe"
    )

    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            return $path
        }
    }

    $searchRoots = @(
        "C:\Program Files\Netease",
        "C:\Program Files (x86)\Netease"
    )

    foreach ($root in $searchRoots) {
        if (-not (Test-Path -LiteralPath $root -PathType Container)) {
            continue
        }

        $found = Get-ChildItem -Path $root -Filter "MuMuManager.exe" -Recurse -File -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($found) {
            return $found.FullName
        }
    }

    throw "MuMuManager.exe not found. Set -MuMuManagerPath explicitly."
}

function Get-DescendantProcessIds {
    param(
        [int]$RootPid
    )

    $allProcesses = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    if (-not $allProcesses) {
        return @()
    }

    $visited = @{}
    $result = @()
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($RootPid)

    while ($queue.Count -gt 0) {
        $currentPid = $queue.Dequeue()
        $children = $allProcesses | Where-Object { [int]$_.ParentProcessId -eq $currentPid } |
            Select-Object -ExpandProperty ProcessId

        foreach ($childPid in $children) {
            $childPid = [int]$childPid
            if ($visited.ContainsKey($childPid)) {
                continue
            }

            $visited[$childPid] = $true
            $result += $childPid
            $queue.Enqueue($childPid)
        }
    }

    return $result
}

function Stop-BaasProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$GraceWaitSeconds = 10
    )

    if ($null -eq $Process) {
        return
    }

    $targetPids = @([int]$Process.Id) + @(Get-DescendantProcessIds -RootPid $Process.Id)
    if (-not $Process.HasExited) {
        $null = $Process.CloseMainWindow()
    }
    Start-Sleep -Seconds $GraceWaitSeconds

    foreach ($procId in $targetPids) {
        $running = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($running) {
            Stop-Process -Id $procId -Force -ErrorAction Stop
        }
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "BAAS Python not found: $PythonPath"
}
if (-not (Test-Path -LiteralPath "$PSScriptRoot\window.py" -PathType Leaf)) {
    throw "BAAS source not found: $PSScriptRoot\window.py"
}

$mumuManager = Resolve-MuMuManagerPath -CustomPath $MuMuManagerPath
Write-Host "Using MuMuManager: $mumuManager"

$baasProcess = $null

try {
    $pythonArguments = '-c "import sys,site,runpy; sys.path.insert(0,''.''); site.addsitedir(''.venv/Lib/site-packages''); runpy.run_path(''window.py'',run_name=''__main__'')"'
    $baasProcess = Start-Process -FilePath $PythonPath -ArgumentList $pythonArguments -WorkingDirectory $PSScriptRoot -WindowStyle Normal -PassThru
    Write-Host "Started BAAS PID: $($baasProcess.Id)"

    $durationSeconds = $DurationMinutes * 60
    Write-Host "Waiting $DurationMinutes minute(s)..."
    Start-Sleep -Seconds $durationSeconds
}
finally {
    $shutdownLog = Join-Path $PSScriptRoot 'log\mumu_shutdown.log'
    try {
        Stop-BaasProcess -Process $baasProcess -GraceWaitSeconds $CloseWaitSeconds
    }
    catch {
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') BAAS close failed: $_" |
            Out-File -LiteralPath $shutdownLog -Encoding utf8 -Append
        throw
    }
    finally {
        Write-Host "Sending MuMu shutdown command for all instances..."
        $shutdownOutput = & $mumuManager control -v all shutdown
        $shutdownExitCode = $LASTEXITCODE
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') MuMu shutdown exit code: $shutdownExitCode" |
            Out-File -LiteralPath $shutdownLog -Encoding utf8 -Append
        $shutdownOutput | Out-File -LiteralPath $shutdownLog -Encoding utf8 -Append
        $shutdownOutput | Write-Output

        if ($shutdownExitCode -ne 0) {
            throw "MuMu shutdown command failed with exit code $shutdownExitCode"
        }

        Write-Host "MuMu shutdown command completed."
    }
}
