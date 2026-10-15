param(
  [string]$Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [string]$CodexHome = (Join-Path $HOME '.codex'),
  [switch]$DryRun,
  [string]$ForceUnpublished
)

$argsList = @((Join-Path $PSScriptRoot 'install.py'), '--source', $Source, '--codex-home', $CodexHome)
if ($DryRun) {
  $argsList += '--dry-run'
}
if ($PSBoundParameters.ContainsKey('ForceUnpublished')) {
  $argsList += @('--force-unpublished', $ForceUnpublished)
}

python @argsList
