# "I cannot reach it from my phone."
#
# Looks at four things, in the order they actually go wrong, and prints the
# address to type. Changes nothing.
#
# Written because the alternative is handing somebody a list of five possible
# causes and asking them to guess which one applies to them. The computer
# already knows the answer to all five.

param([int]$Port = 8000)

$ok   = 'Green'
$bad  = 'Red'
$warn = 'Yellow'

function Line($text, $colour = 'Gray') { Write-Host $text -ForegroundColor $colour }

Write-Host ''
Line '  ============================================================='
Line '    Car Service Invoicing - can a phone or tablet reach it?'
Line '  ============================================================='
Write-Host ''

# --- 1. Is it running, and is it open to anyone but this computer? ---------
Line '  1. Is the application running, and open to the network?'
$listening = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)

if ($listening.Count -eq 0) {
    Line "     NOT RUNNING - nothing is listening on port $Port." $bad
    Line '     Start it with network.bat, then run this check again.'
}
elseif (($listening.LocalAddress -contains '0.0.0.0') -or ($listening.LocalAddress -contains '::')) {
    Line '     Running, and open to the network. Good.' $ok
}
else {
    Line '     Running - but ONLY this computer can reach it.' $bad
    Line ("     It is listening on " + ($listening.LocalAddress -join ', ') + " rather than 0.0.0.0.")
    Line '     That means it was started with run.bat. Close that window'
    Line '     and start it with network.bat instead.' $warn
}
Write-Host ''

# --- 2. Which address should actually be typed? ----------------------------
# The usual mistake is typing an address from an example, or picking one
# belonging to VirtualBox or a VPN rather than the real Wi-Fi.
Line '  2. The address to type on the phone:'
$addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' }

if (-not $addresses) {
    Line '     This computer is not on any network at all.' $bad
}
foreach ($a in $addresses) {
    $real = $a.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN|Ethernet'
    if ($real) {
        Line ("     http://" + $a.IPAddress + ":" + $Port + "    <-- try this  [" + $a.InterfaceAlias + "]") $ok
    } else {
        Line ("     http://" + $a.IPAddress + ":" + $Port + "    (probably not this one)  [" + $a.InterfaceAlias + "]") DarkGray
    }
}
Write-Host ''

# --- 3. Does Windows think this is a network worth trusting? ---------------
# A Wi-Fi marked Public has every inbound connection blocked, whatever the
# firewall rules say. It is the quietest of these failures.
Line '  3. Does Windows trust this network?'
$profiles = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue)
if ($profiles.Count -eq 0) { Line '     No active network found.' $bad }
foreach ($p in $profiles) {
    if ($p.NetworkCategory -eq 'Public') {
        Line ("     '" + $p.Name + "' is set to Public, which blocks this.") $bad
        Line '     Settings > Network & internet > Wi-Fi > click the network,'
        Line '     and set the network profile to Private.' $warn
    } else {
        Line ("     '" + $p.Name + "' is " + $p.NetworkCategory + ". Fine.") $ok
    }
}
Write-Host ''

# --- 4. The firewall -------------------------------------------------------
Line '  4. Is the firewall letting it through?'
$rules = @(
    Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match 'python|uvicorn|Car Service' }
)
if ($rules.Count -gt 0) {
    Line '     A rule allowing it exists. Good.' $ok
} else {
    Line '     No rule for it found.' $warn
    Line '     Windows asks the first time network.bat runs - tick "Private'
    Line '     networks". If that prompt was missed or refused, open Command'
    Line '     Prompt as administrator and paste this one line:'
    Write-Host ''
    Line ('       netsh advfirewall firewall add rule name="Car Service Invoicing" dir=in action=allow protocol=TCP localport=' + $Port + ' profile=private') Cyan
}

Write-Host ''
Line '  ============================================================='
Line '    If all four are good and the phone still cannot open it,'
Line '    the Wi-Fi is keeping devices apart from each other (guest'
Line '    mode, or "client isolation" on the router). Check that the'
Line '    phone is on the same network name as this computer - not'
Line '    the guest network - and not on mobile data.'
Line '  ============================================================='
Write-Host ''
