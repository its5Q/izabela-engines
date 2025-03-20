.\conda_install\Scripts\conda shell.powershell hook | Out-String | ?{$_} | Invoke-Expression
conda activate .\conda_env
set IZABELA_USE_CUDA=1
fastapi run