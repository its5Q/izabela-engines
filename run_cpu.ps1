.\conda_install\Scripts\conda shell.powershell hook | Out-String | ?{$_} | Invoke-Expression
$env:Path = "$env:Path;$pwd\conda_env\Library\bin"
. config.ps1
conda activate .\conda_env
fastapi run --port $port --host 127.0.0.1