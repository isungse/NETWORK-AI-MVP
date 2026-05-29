param(
  [string]$HostName = "172.16.1.1",
  [int]$Port = 23,
  [string]$CredentialPath = "$env:USERPROFILE\backbone_admin.cred.xml",
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Commands = @(
    "terminal length 0",
    "show version",
    "show running-config | include ^hostname",
    "show ip interface brief",
    "show interfaces description",
    "show cdp neighbors",
    "show lldp neighbors"
  )
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $CredentialPath)) {
  throw "Credential file not found: $CredentialPath"
}

$cred = Import-Clixml -LiteralPath $CredentialPath
$user = $cred.UserName
$password = $cred.GetNetworkCredential().Password

$client = [System.Net.Sockets.TcpClient]::new()
$client.ReceiveTimeout = 5000
$client.SendTimeout = 5000
$client.Connect($HostName, $Port)
$stream = $client.GetStream()
$encoding = [System.Text.Encoding]::ASCII

function Send-Bytes([byte[]]$bytes) {
  $stream.Write($bytes, 0, $bytes.Length)
  $stream.Flush()
}

function Send-Line([string]$line) {
  $bytes = $encoding.GetBytes($line + "`r`n")
  Send-Bytes $bytes
}

function Read-Telnet([int]$QuietMs = 700, [int]$MaxMs = 12000) {
  $buffer = New-Object byte[] 4096
  $text = New-Object System.Text.StringBuilder
  $start = Get-Date
  $lastData = Get-Date

  while (((Get-Date) - $start).TotalMilliseconds -lt $MaxMs) {
    if (-not $stream.DataAvailable) {
      Start-Sleep -Milliseconds 100
      if ($text.Length -gt 0 -and ((Get-Date) - $lastData).TotalMilliseconds -ge $QuietMs) {
        break
      }
      continue
    }

    $read = $stream.Read($buffer, 0, $buffer.Length)
    if ($read -le 0) { break }
    $lastData = Get-Date

    for ($i = 0; $i -lt $read; $i++) {
      $b = $buffer[$i]
      if ($b -eq 255) {
        if ($i + 1 -ge $read) { continue }
        $cmd = $buffer[++$i]
        if ($cmd -eq 255) {
          [void]$text.Append([char]255)
          continue
        }
        if ($cmd -eq 251 -or $cmd -eq 252 -or $cmd -eq 253 -or $cmd -eq 254) {
          if ($i + 1 -ge $read) { continue }
          $opt = $buffer[++$i]
          if ($cmd -eq 251) { Send-Bytes ([byte[]](255, 254, $opt)) } # WILL -> DONT
          elseif ($cmd -eq 253) { Send-Bytes ([byte[]](255, 252, $opt)) } # DO -> WONT
          continue
        }
        if ($cmd -eq 250) {
          while ($i + 1 -lt $read) {
            $i++
            if ($buffer[$i] -eq 255 -and $i + 1 -lt $read -and $buffer[$i + 1] -eq 240) {
              $i++
              break
            }
          }
          continue
        }
        continue
      }

      if ($b -eq 0) { continue }
      [void]$text.Append([char]$b)
    }
  }

  return $text.ToString()
}

function Wait-For([string[]]$Patterns, [int]$MaxMs = 15000) {
  $all = New-Object System.Text.StringBuilder
  $start = Get-Date
  while (((Get-Date) - $start).TotalMilliseconds -lt $MaxMs) {
    $chunk = Read-Telnet -QuietMs 250 -MaxMs 1500
    if ($chunk.Length -gt 0) {
      [void]$all.Append($chunk)
      foreach ($pattern in $Patterns) {
        if ($all.ToString() -match $pattern) {
          return $all.ToString()
        }
      }
    }
  }
  return $all.ToString()
}

try {
  [void](Wait-For @("(?i)username:", "(?i)login:", "(?i)password:", "[>#]\s*$") 12000)
  $banner = Read-Telnet -QuietMs 300 -MaxMs 1000

  if ($banner -match "(?i)username:" -or $banner -match "(?i)login:" -or $banner.Length -eq 0) {
    Send-Line $user
    [void](Wait-For @("(?i)password:") 10000)
  }

  Send-Line $password
  $loginResult = Wait-For @("[>#]\s*$", "(?i)authentication failed", "(?i)login invalid", "(?i)incorrect") 15000

  if ($loginResult -match "(?i)authentication failed|login invalid|incorrect") {
    throw "Login failed."
  }

  foreach ($cmd in $Commands) {
    Send-Line $cmd
    $output = Wait-For @("[>#]\s*$", "--More--") 20000
    while ($output -match "--More--") {
      Send-Bytes ($encoding.GetBytes(" "))
      $output += Wait-For @("[>#]\s*$", "--More--") 20000
    }
    "===== $cmd ====="
    $output
  }

  Send-Line "exit"
}
finally {
  if ($stream) { $stream.Dispose() }
  if ($client) { $client.Dispose() }
}
