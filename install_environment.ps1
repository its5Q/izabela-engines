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

conda create --no-shortcuts -y -k --prefix "./conda_env" python=3.10

conda activate base
conda activate .\conda_env

Function Read-YesNoChoice {
	Param (
        [Parameter(Mandatory=$true)][String]$Title,
		[Parameter(Mandatory=$true)][String]$Message,
		[Parameter(Mandatory=$false)][Int]$DefaultOption = 0
    )

	$No = New-Object System.Management.Automation.Host.ChoiceDescription '&No', 'No'
	$Yes = New-Object System.Management.Automation.Host.ChoiceDescription '&Yes', 'Yes'
	$Options = [System.Management.Automation.Host.ChoiceDescription[]]($No, $Yes)

	return $host.ui.PromptForChoice($Title, $Message, $Options, $DefaultOption)
}

$useCUDA = Read-YesNoChoice -Title "Enable NVIDIA GPU support?" -Message "This will download the CUDA runtime which will take about 6GB of disk space, but your GPU will be used instead of your CPU for engines which support it and the voice generation will be much faster. (you can always run on CPU with the run_cpu.cmd script)" -DefaultOption 1

python -m pip install -r requirements.txt

switch($useCUDA) {
    1 {
        conda install -y nvidia/label/cuda-12.8.1::cuda-runtime
        conda install -y nvidia::cudnn=9.8.0.87=cuda12.8
        python -m pip uninstall -y onnxruntime
        python -m pip install onnxruntime-gpu
    }
}

conda clean --all --force-pkgs-dirs -y

write "Installation complete! If you didn't see any stuff in red above, you should be good. If there were errors, or the run_*.cmd scripts don't work after the environment installation, please file an issue on GitHub."