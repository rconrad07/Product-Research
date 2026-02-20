# User evaluation for `output/loyalty_program_analysis_report.html`

## Overall

- This report was very compelling, especially the metrics around loyalty program usage and customer satisfaction. However, with URL links that didn't work, it was hard to validate or trust the claims made in the report.
- This report is formatted perfectly and the information is at the right level of detail.

## URL Citations

- The URL deeplinks were still not successful. Perform a double check on the URL's and make sure they are correct (e.g. resolve to a 200 status code)
- Below is an example from another project that successfully validates URLs for report output. Consider using it or something similar:

powershell
param (
    [Parameter(Mandatory = $false)]
    [string]$ReportPath,
    [switch]$PatchBroken
)

$ErrorActionPreference = "Continue"

# If no path provided, find the latest report

if (-not $ReportPath) {
    $reportsDir = Join-Path $PSScriptRoot "..\reports"
    $latest = Get-ChildItem -Path $reportsDir -Filter "Daily_Report_*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $latest) {
        Write-Host "[ERROR] No reports found." -ForegroundColor Red
        exit 1
    }
    $ReportPath = $latest.FullName
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  URL Validator" -ForegroundColor Cyan
Write-Host "  File: $(Split-Path $ReportPath -Leaf)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$content = Get-Content $ReportPath -Raw

# Extract all href URLs (skip anchors, javascript:, and file://)

$hrefPattern = 'href="(https?://[^"]+)"'
$hrefMatches = [regex]::Matches($content, $hrefPattern)

# URLs to skip (fonts, CDNs, display resources — not citations)

$skipDomains = @("fonts.googleapis.com", "fonts.gstatic.com")
$urls = @()
foreach ($m in $hrefMatches) {
    $url = $m.Groups[1].Value
    $uriCheck = [System.Uri]::new($url)
    $skip = $false
    foreach ($sd in $skipDomains) {
        if ($uriCheck.Host -eq $sd) { $skip = $true; break }
    }
    if (-not $skip -and $url -notin $urls) {
        $urls += $url
    }
}

if ($urls.Count -eq 0) {
    Write-Host "[WARN] No external URLs found in the report." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($urls.Count) unique external URLs to validate." -ForegroundColor White
Write-Host ""

$passedCount = 0
$failedCount = 0
$results = @()

foreach ($url in $urls) {
    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 10 -UseBasicParsing -MaximumRedirection 3 -ErrorAction Stop
        $statusCode = $response.StatusCode

        # Check if URL path is just "/" (homepage detection)
        $uriObj = [System.Uri]::new($url)
        $pathIsRoot = ($uriObj.AbsolutePath -eq "/") -or ($uriObj.AbsolutePath -eq "")

        if ($statusCode -ge 200 -and $statusCode -lt 400 -and -not $pathIsRoot) {
            Write-Host "  [PASS] $statusCode - $url" -ForegroundColor Green
            $passedCount++
            $results += [PSCustomObject]@{ URL = $url; Status = $statusCode; Result = "PASS"; Note = "" }
        }
        elseif ($pathIsRoot) {
            Write-Host "  [WARN] $statusCode - HOMEPAGE - $url" -ForegroundColor Yellow
            $failedCount++
            $results += [PSCustomObject]@{ URL = $url; Status = $statusCode; Result = "HOMEPAGE"; Note = "Link points to site root" }
        }
        else {
            Write-Host "  [FAIL] $statusCode - $url" -ForegroundColor Red
            $failedCount++
            $results += [PSCustomObject]@{ URL = $url; Status = $statusCode; Result = "FAIL"; Note = "HTTP $statusCode" }
        }
    }
    catch {
        $errMsg = $_.Exception.Message
        Write-Host "  [FAIL] ERROR - $url" -ForegroundColor Red
        Write-Host "         $errMsg" -ForegroundColor DarkGray
        $failedCount++
        $results += [PSCustomObject]@{ URL = $url; Status = "ERR"; Result = "FAIL"; Note = $errMsg }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Results: $passedCount passed, $failedCount failed of $($urls.Count)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

## Avoid accidental hyperbole

- The metrics that were cited in this report are extremly compelling, which is why I am so frustrated at the lack of ability to trace them back to their source. They feel almost unbelievable, and I want to know where they came from.
  - Out of procaution, I would like to institute some new rules around citations:
    - QUOTE SELECTION RULES
      - Start where the thought begins, and continue until fully expressed
      - Include reasoning, not just conclusions
      - Keep hedges and qualifiers — they signal uncertainty
      - Include emotional language when present
      - Do not combine statements from different parts of the citation
    - Quote Verification
      - Confirm the quote exists verbatim in the source
      - If the quote is a close paraphrase but not exact, flag it and provide the actual wording
      - If the quote cannot be located, do not include it in the report
