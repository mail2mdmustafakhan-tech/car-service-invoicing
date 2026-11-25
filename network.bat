@echo off
REM ===========================================================================
REM  Start Car Service Invoicing so a tablet can reach it.
REM
REM  run.bat serves this computer only, which is the right default: nothing
REM  can reach it, so nothing has to be trusted. This one serves the whole
REM  local network, so the iPad on the counter and the Android tablet at the
REM  ramp can open it too.
REM
REM  Read this before using it, once:
REM
REM    There is no password on this application. Anyone who can reach the
REM    network can open it, read every customer's details and change any
REM    invoice. That is fine on the workshop's own Wi-Fi with a password on
REM    it. It is NOT fine on a guest network, a shared network in a building,
REM    or anything a customer in the waiting area can join.
REM
REM    If the workshop's Wi-Fi has a guest network, keep this off it. If it
REM    does not have one, that is worth asking for -- the customers in the
REM    waiting room are on your network otherwise.
REM
REM  The first run asks Windows Firewall for permission. Tick "Private
REM  networks" and leave "Public networks" unticked.
REM ===========================================================================

set CARSERVICE_HOST=0.0.0.0
call "%~dp0run.bat"
