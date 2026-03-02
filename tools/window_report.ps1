param(
  [Parameter(Mandatory=$true)][int]$NMin,
  [Parameter(Mandatory=$true)][int]$NMax,
  [Parameter(Mandatory=$true)][string]$WitnessCsv,
  [int]$Step = 97
)

Write-Host "=== Window $NMin .. $NMax ==="

# Expanded witness stats
$w = Import-Csv $WitnessCsv
$expandedCount = $w.Count
$semiprimeCount = @($w | Where-Object { $_.semiprime_kind -eq "p*q" }).Count
$sqCount = @($w | Where-Object { $_.semiprime_kind -eq "p^2" }).Count

$expandedSemiprimeRate = if ($expandedCount -gt 0) { $semiprimeCount / $expandedCount } else { 0.0 }

Write-Host ("expanded_count: {0}" -f $expandedCount)
Write-Host ("expanded_semiprime_pq: {0}" -f $semiprimeCount)
Write-Host ("expanded_prime_square_p2: {0}" -f $sqCount)
Write-Host ("expanded_semiprime_rate_pq: {0:N6}" -f $expandedSemiprimeRate)

# Baseline sampler (calls your deterministic python)
$py = "python tools\sample_semiprime_rate.py --n-min $NMin --n-max $NMax --step $Step"
Write-Host ("baseline_cmd: {0}" -f $py)

$baselineOut = & python tools\sample_semiprime_rate.py --n-min $NMin --n-max $NMax --step $Step
$baselineText = ($baselineOut -join "`n")
Write-Host $baselineText

# Parse baseline semiprime_rate line
$baselineRateLine = $baselineOut | Where-Object { $_ -like "semiprime_rate:*" }
$baselineRate = [double]($baselineRateLine.Split(":")[1].Trim())

$enrichment = if ($baselineRate -gt 0) { $expandedSemiprimeRate / $baselineRate } else { 0.0 }
Write-Host ("enrichment_ratio (expanded_pq / baseline): {0:N3}" -f $enrichment)