.\conda_install\Scripts\conda shell.powershell hook | Out-String | ?{$_} | Invoke-Expression
conda activate .\conda_env
$env:IZABELA_USE_CUDA=1
$env:Path = "$env:Path;$pwd\conda_env\Library\bin"
fastapi run