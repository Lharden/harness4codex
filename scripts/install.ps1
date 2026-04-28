param(
  [string]$Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [string]$CodexHome = (Join-Path $HOME '.codex'),
  [switch]$DryRun
)

$argsList = @((Join-Path $PSScriptRoot 'install.py'), '--source', $Source, '--codex-home', $CodexHome)
if ($DryRun) {
  $argsList += '--dry-run'
}

python @argsList
