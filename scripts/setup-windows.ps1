param(
    [ValidateSet('Gpu','Remote')][string]$Mode='Gpu',
    [string]$Distribution='Ubuntu',
    [ValidateRange(1024,65535)][int]$Port=8765,
    [string]$AppDirectory,
    [switch]$InstallSystemDependencies,
    [switch]$Check
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
function Invoke-Wsl([string[]]$CommandArguments) {
    & wsl.exe -d $Distribution --exec @CommandArguments
    if($LASTEXITCODE -ne 0){throw 'WSL command failed. Resolve the diagnostic above and retry.'}
}
if(-not(Get-Command wsl.exe -ErrorAction SilentlyContinue)){throw 'Install WSL2 and Ubuntu first: wsl --install -d Ubuntu. Restart Windows if requested.'}
$wslRoot=((& wsl.exe -d $Distribution --exec wslpath -a -u ($root.Replace('\','/')))|Out-String).Trim()
if($LASTEXITCODE -ne 0 -or -not $wslRoot){throw 'Ubuntu is not ready. Complete its first launch and create a Linux user.'}
$preflight=@('bash',"$wslRoot/scripts/setup-backend.sh",'--check')
if($Mode -eq 'Gpu'){$preflight+='--gpu'}
Invoke-Wsl $preflight
if($Check){return}
foreach($command in @('node','git','tar.exe')){
    if(-not(Get-Command $command -ErrorAction SilentlyContinue)){throw "Install $command before running setup. See docs/INSTALL.md."}
}
$nodeVersion=[version]((& node --version).Trim().TrimStart('v'))
if($nodeVersion -lt [version]'22.12.0'){throw 'Node.js 22.12 or later is required.'}
Push-Location $root
$archive=Join-Path ([IO.Path]::GetTempPath()) ("meetsift-"+[guid]::NewGuid().ToString('N')+'.tar')
try{
    & node scripts/check-public-surface.mjs
    if($LASTEXITCODE -ne 0){throw 'Source export failed its public-surface check.'}
    $files=@(& git -c core.quotePath=false ls-files --cached --others --exclude-standard | Where-Object {$_ -match '^(backend|scripts)/' -and (Test-Path -LiteralPath $_ -PathType Leaf)} | Sort-Object -Unique)
    if($LASTEXITCODE -ne 0 -or $files.Count -lt 5){throw 'Run setup from a complete Git checkout.'}
    & tar.exe -cf $archive -C $root @files
    if($LASTEXITCODE -ne 0){throw 'Backend source export failed.'}
    $wslHome=((& wsl.exe -d $Distribution --exec printenv HOME)|Out-String).Trim()
    if($LASTEXITCODE -ne 0 -or -not $wslHome){throw 'WSL home directory was not found.'}
    $backendSource="$wslHome/.local/share/meetsift/source"
    $wslArchive=((& wsl.exe -d $Distribution --exec wslpath -a -u ($archive.Replace('\','/')))|Out-String).Trim()
    if($LASTEXITCODE -ne 0){throw 'Could not locate the temporary source export in WSL.'}
    Invoke-Wsl @('mkdir','-p',$backendSource)
    Invoke-Wsl @('tar','-xf',$wslArchive,'-C',$backendSource)
    $setup=@('bash',"$backendSource/scripts/setup-backend.sh")
    if($Mode -eq 'Gpu'){$setup+='--gpu'}
    if($InstallSystemDependencies){$setup+='--system-deps'}
    Invoke-Wsl $setup
    if($AppDirectory){
        $AppDirectory=(Resolve-Path -LiteralPath $AppDirectory).Path
        if(-not(Test-Path -LiteralPath (Join-Path $AppDirectory 'MeetSift.exe'))){throw 'AppDirectory must contain MeetSift.exe and its resources folder.'}
    }else{
        & npm.cmd ci
        if($LASTEXITCODE -ne 0){throw 'Desktop dependency installation failed.'}
        & node node_modules/electron/install.js
        if($LASTEXITCODE -ne 0){throw 'Electron binary installation failed.'}
        & npm.cmd run build
        if($LASTEXITCODE -ne 0){throw 'Desktop build failed.'}
    }
    $state=Join-Path $root '.local-data'
    [IO.Directory]::CreateDirectory($state)|Out-Null
    $config=@{distribution=$Distribution;backendSource=$backendSource;port=$Port;appDirectory=$AppDirectory}
    [IO.File]::WriteAllText((Join-Path $state 'windows.json'),($config|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
    Write-Host 'MeetSift is ready. Run: .\scripts\start-windows.ps1'
}finally{
    if(Test-Path -LiteralPath $archive){Remove-Item -LiteralPath $archive -Force}
    Pop-Location
}
