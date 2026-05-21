$ErrorActionPreference = "Stop"

$Proxy = "http://127.0.0.1:7890"
$Repo = "G:/rhino_autoModeling"
$SkillsRepo = Join-Path $env:USERPROFILE ".codex/vendor_imports/skills"

Write-Host "Checking local proxy $Proxy ..."
$proxyPortOk = (Test-NetConnection -ComputerName 127.0.0.1 -Port 7890).TcpTestSucceeded
if (-not $proxyPortOk) {
    throw "Proxy port 127.0.0.1:7890 is not reachable. Start Clash or update the proxy port in this script first."
}

Write-Host "Configuring Git proxy ..."
git config --global http.proxy $Proxy

$safeDirs = @(git config --global --get-all safe.directory 2>$null)
if (($safeDirs -notcontains "G:/rhino_autoModeling") -and ($safeDirs -notcontains "G:\rhino_autoModeling")) {
    git config --global --add safe.directory "G:/rhino_autoModeling"
}

Write-Host "Configuring repository-local proxy ..."
git -C $Repo config --local http.proxy $Proxy

if (Test-Path (Join-Path $SkillsRepo ".git")) {
    Write-Host "Configuring Codex recommended-skills repository proxy ..."
    git -C $SkillsRepo config --local http.proxy $Proxy
}

Write-Host "Testing current repo remote ..."
git -C $Repo remote show origin

Write-Host "Testing OpenAI skills remote ..."
git ls-remote https://github.com/openai/skills.git HEAD

Write-Host "Done. Restart Codex Desktop and open this workspace again."
