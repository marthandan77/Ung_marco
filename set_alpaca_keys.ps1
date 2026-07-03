$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $PSScriptRoot ".env.example") $envPath
}

$keyId = Read-Host "Paste new Alpaca API key ID"
$secret = Read-Host "Paste new Alpaca secret key" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)

try {
    $plainSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $lines = Get-Content -Path $envPath

    $updates = @{
        "MARKET_DATA_PROVIDER" = "auto"
        "ALPACA_API_KEY_ID" = $keyId
        "ALPACA_SECRET_KEY" = $plainSecret
        "ALPACA_STOCK_FEED" = "iex"
    }

    foreach ($name in $updates.Keys) {
        $value = $updates[$name]
        if ($lines -match "^$name=") {
            $lines = $lines -replace "^$name=.*", "$name=$value"
        } else {
            $lines += "$name=$value"
        }
    }

    Set-Content -Path $envPath -Value $lines
    Write-Host "Alpaca credentials saved to .env"
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
