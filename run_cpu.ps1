.\conda_install\Scripts\conda shell.powershell hook | Out-String | ?{$_} | Invoke-Expression
conda activate .\conda_env
fastapi run