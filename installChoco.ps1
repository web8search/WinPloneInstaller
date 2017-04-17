#
# installChoco.ps1
#
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) { Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs; exit }
Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy unrestricted -Force
iwr https://chocolatey.org/install.ps1 -UseBasicParsing | iex
choco feature enable -n=allowGlobalConfirmation
choco feature enable -n=virusCheck
choco feature enable -n=allowEmptyChecksums
choco install pscx
"#" | Add-Content '..\installLog.txt'
"choco installed" | Add-Content '..\installLog.txt'