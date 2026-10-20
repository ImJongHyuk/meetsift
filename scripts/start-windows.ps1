param([switch]$SoftwareRendering)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$configPath=Join-Path $root '.local-data/windows.json'
if(-not(Test-Path -LiteralPath $configPath)){throw 'Run scripts/setup-windows.ps1 first.'}
$config=Get-Content -Raw -LiteralPath $configPath|ConvertFrom-Json
$origin="http://127.0.0.1:$($config.port)"
$token=((& wsl.exe -d $config.distribution --exec cat "$($config.backendSource)/.local-data/api-token")|Out-String).Trim()
if($LASTEXITCODE -ne 0 -or -not $token){throw 'Local backend token is missing. Re-run setup.'}
$headers=@{Authorization='Bearer '+$token}
try{$health=Invoke-RestMethod "$origin/health" -TimeoutSec 2}catch{$health=$null}
if($health.ok){
    try{Invoke-RestMethod "$origin/api/jobs" -Headers $headers -TimeoutSec 3|Out-Null}catch{throw 'This port belongs to another backend. Stop that backend or re-run setup with a different -Port.'}
}else{
    $state=Join-Path $root '.local-data'
    $wslArguments=@('-d',$config.distribution,'--exec','bash',"$($config.backendSource)/scripts/run-backend.sh",'--port',[string]$config.port)
    $quotedArguments=($wslArguments|ForEach-Object {if($_ -match '\s'){ '"'+$_.Replace('"','\"')+'"' }else{ $_ }}) -join ' '
    $worker=Start-Process -FilePath 'wsl.exe' -ArgumentList $quotedArguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $state 'backend-stdout.log') -RedirectStandardError (Join-Path $state 'backend-stderr.log')
    [IO.File]::WriteAllText((Join-Path $state 'backend-windows.pid'),[string]$worker.Id)
    for($attempt=0;$attempt -lt 45;$attempt++){
        Start-Sleep -Seconds 1
        try{Invoke-RestMethod "$origin/api/jobs" -Headers $headers -TimeoutSec 2|Out-Null;$connected=$true;break}catch{}
    }
    if(-not $connected){throw 'Backend did not become ready. Inspect .local-data/backend-stderr.log in this checkout.'}
}
$previous=@{}
foreach($name in @('MEETING_EXTERNAL_BACKEND','MEETING_BACKEND_URL','MEETING_API_TOKEN')){$previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try{
    $env:MEETING_EXTERNAL_BACKEND='1'
    $env:MEETING_BACKEND_URL=$origin
    $env:MEETING_API_TOKEN=$token
    $arguments=@()
    if($config.appDirectory){
        $executable=Join-Path $config.appDirectory 'MeetSift.exe'
        $workingDirectory=$config.appDirectory
    }else{
        $executable=Join-Path $root 'node_modules/electron/dist/electron.exe'
        $workingDirectory=$root
        $arguments+= '.'
    }
    if($SoftwareRendering){$arguments+='--disable-gpu'}
    if(-not(Test-Path -LiteralPath $executable)){throw 'Desktop executable is missing. Re-run setup.'}
    $launch=@{FilePath=$executable;WorkingDirectory=$workingDirectory}
    if($arguments.Count){$launch.ArgumentList=$arguments}
    Start-Process @launch
}finally{
    foreach($name in $previous.Keys){[Environment]::SetEnvironmentVariable($name,$previous[$name],'Process')}
}
