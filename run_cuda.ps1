.\conda_install\Scripts\conda shell.powershell hook | Out-String | ?{$_} | Invoke-Expression
$env:Path = "$env:Path;$pwd\conda_env\Library\bin"
. config.ps1
conda activate .\conda_env
$env:IZABELA_USE_CUDA=1
fastapi run --port $port  --host 127.0.0.1