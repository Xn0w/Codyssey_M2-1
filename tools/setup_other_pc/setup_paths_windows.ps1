# 다른 PC 에서 UGV 시험 스크립트의 절대 경로 (C:\Users\수다쟁이고양이들\...) 를 그대로 쓰게 하는 연결 (관리자 PowerShell 에서 한 번 실행).
# C:\Users\수다쟁이고양이들  →  이 PC 의 실제 사용자 폴더 (junction). WSL /mnt/c/Users/수다쟁이고양이들 와 Git Bash /c/Users/수다쟁이고양이들 도 이 연결로 해결됨.
# 전제: 저장소 3 개가 <사용자 폴더>\Documents\GitHub\ 아래에 ADAIR, ADAIR_wt_hook, ADAIR_wt_vehicle 로 있음.
param([string]$Target = $env:USERPROFILE)
$Link = 'C:\Users\수다쟁이고양이들'
if (Test-Path $Link) {
    $it = Get-Item $Link -Force
    if ($it.LinkType) { Write-Host "이미 연결 있음: $Link -> $($it.Target)" } else { Write-Host "이미 실제 폴더 있음 (원래 PC): $Link — 아무것도 하지 않음" }
} else {
    New-Item -ItemType Junction -Path $Link -Target $Target | Out-Null
    Write-Host "연결 만듦: $Link -> $Target"
}
foreach ($r in 'ADAIR','ADAIR_wt_hook','ADAIR_wt_vehicle') {
    $p = Join-Path $Link "Documents\GitHub\$r"
    if (Test-Path $p) { Write-Host "확인: $p" } else { Write-Host "없음 (clone/worktree 필요): $p" }
}
