# Prints the address other devices on the network should use for this
# computer, and nothing else. One line, no decoration, so a batch file can
# read it straight into a variable.
#
# Not `ipconfig | findstr "IPv4 Address"`, which was the first attempt: that
# string is translated, so it finds nothing at all on a Windows installed in
# Arabic, and it cannot tell the workshop's Wi-Fi from VirtualBox's adapter
# or a VPN. Asking Windows which interface is which is both language-proof
# and correct.

$candidate =
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -ne '127.0.0.1' -and
        $_.PrefixOrigin -ne 'WellKnown' -and          # not a 169.254 self-assignment
        $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN|Ethernet'
    } |
    Sort-Object -Property @{ Expression = { $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN' } } -Descending |
    Select-Object -First 1 -ExpandProperty IPAddress

if ($candidate) { Write-Output $candidate }
