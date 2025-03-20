# Credit for parts of Miniconda installation
# https://gist.github.com/CypherpunkSamurai/359503fa3a23ea5e493c5eeeaf2de8d4

# Get Miniconda
Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"  -OutFile "miniconda.exe"

# Extract the Miniconda package
cmd.exe /c "miniconda.exe /InstallationType=JustMe /AddToPath=0 /S /RegisterPython=0 /NoRegistry=1 /NoScripts=1 /NoShortcuts=1 /KeepPkgCache=0 /D=$PWD\conda_install"

Remove-Item miniconda.exe

# Move _conda.exe to conda.exe
Move-Item .\conda_install\_conda.exe .\conda_install\conda.exe

# Note:
# Be sure to add the conda folder to path to use conda
$env:Path = "$env:Path;$pwd\conda_install;$pwd\conda_install\Scripts"

# Optionally
New-Item -ItemType File -Path .\conda_install\PATH.txt -Value "$pwd\conda_install;$pwd\conda_install\Scripts" -Force | Out-Null
New-Item -ItemType File -Path .\conda_install\activate_conda.ps1 -Value ('$env:Path = "$env:Path;$(Get-Content -Path ' + "$PWD\conda_install\PATH.txt" + ')"') -Force | Out-Null

.\conda_install\Scripts\conda shell.powershell hook | Out-String | ?{$_} | Invoke-Expression

.\conda_install\conda.exe create --no-shortcuts -y -k --prefix "./conda_env" python=3.10

conda activate base
conda activate .\conda_env

conda install -y nvidia/label/cuda-12.8.1::cuda-runtime
conda install -y nvidia::cudnn=9.8.0.87=cuda12.8

python -m pip install -r requirements.txt
python -m pip uninstall -y onnxruntime
python -m pip install onnxruntime-gpu

conda clean --all --force-pkgs-dirs -y