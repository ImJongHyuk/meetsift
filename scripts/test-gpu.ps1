param(
    [Parameter(Mandatory=$true)][string]$AudioPath,
    [ValidateRange(1,100)][int]$MinSpeakers=1,
    [ValidateRange(1,86400)][int]$TimeoutSeconds=1800,
    [string]$Distribution='Ubuntu',
    [switch]$InstallSystemDependencies,
    [switch]$SkipSetup,
    [switch]$KeepResults
)
$ErrorActionPreference='Stop'
$audio=Get-Item -LiteralPath $AudioPath
if($audio.PSIsContainer -or $audio.Length -eq 0){throw 'Supply an existing nonempty recording file.'}
$root=Split-Path -Parent $PSScriptRoot
if(-not $SkipSetup){
    $setup=@{Mode='Gpu';Distribution=$Distribution}
    if($InstallSystemDependencies){$setup.InstallSystemDependencies=$true}
    & (Join-Path $PSScriptRoot 'setup-windows.ps1') @setup
}
$configPath=Join-Path $root '.local-data/windows.json'
if(-not(Test-Path -LiteralPath $configPath)){throw 'Run without -SkipSetup to install first.'}
$config=Get-Content -Raw -LiteralPath $configPath|ConvertFrom-Json
$previousEncoding=[Console]::OutputEncoding
try{
    # wslpath writes UTF-8, including Korean filenames, on Windows PowerShell 5.1.
    [Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
    $wslAudio=((& wsl.exe -d $config.distribution --exec wslpath -a -u ($audio.FullName.Replace('\','/')))|Out-String).Trim()
    if($LASTEXITCODE -ne 0 -or -not $wslAudio){throw 'Recording path could not be mapped into WSL.'}
}finally{
    [Console]::OutputEncoding=$previousEncoding
}
$arguments=@("$($config.backendSource)/scripts/test-gpu-recording.py",'--skip-setup','--audio',$wslAudio,
             '--min-speakers',[string]$MinSpeakers,'--timeout',[string]$TimeoutSeconds)
if($KeepResults){$arguments+='--keep-results'}
& wsl.exe -d $config.distribution --exec "$($config.backendSource)/backend/.venv/bin/python" @arguments
if($LASTEXITCODE -ne 0){throw 'GPU recording integration test failed. See the diagnostic above.'}
