param(
    [string]$AdaRoot = (Get-Location).Path,
    [string]$TaskName = "ADA Autonomous"
)

$xmlPath = Join-Path $AdaRoot "deploy\windows\ada-task.xml"
if (-not (Test-Path $xmlPath)) { throw "No se encontró $xmlPath" }
$xml = (Get-Content -Raw -Encoding Unicode $xmlPath).Replace("%ADA_ROOT%", $AdaRoot)
$temp = Join-Path $env:TEMP "ada-task.xml"
Set-Content -Path $temp -Value $xml -Encoding Unicode
try {
    schtasks.exe /Create /TN $TaskName /XML $temp /F | Out-Host
} finally {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}
Write-Host "Tarea '$TaskName' instalada. Verificá con: schtasks /Query /TN '$TaskName'"
