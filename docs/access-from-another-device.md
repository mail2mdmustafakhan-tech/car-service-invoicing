# Using it from a tablet, a phone, or another computer

The application runs on one PC. Other devices reach it over the workshop's
own network, through an ordinary browser — Safari, Chrome, anything. There is
nothing to install on the tablet.

Before anything else, the one sentence that matters:

> **There is no password on this application.** Anyone who can reach the
> network can open it, read every customer's details and change any invoice.

That is fine on a workshop network only staff know the password to. It is not
fine if customers in the waiting area are on the same one — and in most small
businesses, they are. See [Who can get in](#who-can-get-in) below.

---

## Setting it up

### 1. Start it so the network can reach it

On the PC, double-click **`network.bat`** instead of `run.bat`.

Both run the same application. `run.bat` serves that computer only, which is
the right default — nothing can reach it, so nothing has to be trusted.
`network.bat` opens it to the local network.

The first time, Windows asks whether to allow it through the firewall. Tick
**Private networks**. Leave **Public networks** unticked.

### 2. Find the address

The window that opens prints it:

```
    On a tablet or phone on the same Wi-Fi:
      http://192.168.0.17:8000
```

**The numbers will be yours, not those.** Any address written in a guide or a
chat is an example of the shape. Three ways to get the real one:

1. The `network.bat` window prints it, as above.
2. Double-click **`check-network.bat`** — it lists every address the PC has,
   with the Wi-Fi one marked `<-- try this`.
3. Windows: Settings → Network & internet → Wi-Fi → click the network name →
   scroll to **IPv4 address**.

### 3. Open it on the tablet

Type the whole thing, including `http://` and `:8000`:

```
http://192.168.0.17:8000
```

Safari may warn that the connection is "not secure". On your own network,
reaching your own computer, that is expected and not a problem — it only
means the traffic is not encrypted, and it never leaves the building.

### 4. Add it to the home screen

So it opens like an app rather than a browser tab:

- **iPad / iPhone (Safari):** Share button → Add to Home Screen.
- **Android (Chrome):** ⋮ menu → Add to Home screen.

It takes the workshop's logo as its icon and opens in its own window with no
browser bars.

### 5. Stop the address from changing

Ask whoever looks after the router to **reserve** that address for this PC —
sometimes called a DHCP reservation or a static lease. Without it the router
may hand the PC a different address one day, and every tablet will stop
working with no visible reason and nothing to explain it.

---

## Using it on a tablet

The controls are sized for fingers rather than a mouse: every button, box
and dropdown is at least 44 pixels, and tapping a tick-box's label works as
well as tapping the box.

**Hold the inspection sheet in landscape.** It fits the screen exactly that
way. In portrait it is about 140 pixels wider than the screen and has to be
scrolled sideways, which is tiring across eighteen rows.

Two things that work better on a tablet than on the PC:

- **Printing** goes through Safari's share sheet to any AirPrint printer.
- **The photo fields open the camera**, so a car's condition can be
  photographed straight onto the contract while standing next to it.

---

## When a device cannot connect

Double-click **`check-network.bat`** on the PC while the application is
running. It changes nothing. It checks the four things that actually go
wrong, in the order they go wrong, and tells you which one is yours.

### 1. "Running, but ONLY this computer can reach it"

You started it with `run.bat`. Close that window and use `network.bat`.

This is invisible from the tablet — the page simply never loads — which is
why it is the first thing the check looks at.

### 2. The address

The check prints every address the PC has. Use the one marked `<-- try this`.

The usual mistakes are typing an address from an example, and picking one
belonging to VirtualBox, a VPN or Docker rather than the real Wi-Fi. The
check marks those as *probably not this one*.

### 3. "Set to Public, which blocks this"

Windows treats a network it does not trust as Public and blocks every
incoming connection, whatever the firewall rules say. It is the quietest of
these failures — nothing announces it.

Settings → Network & internet → Wi-Fi → click the network → set the network
profile to **Private**.

### 4. No firewall rule

Windows asks the first time `network.bat` runs. If that prompt was missed or
refused, the check prints the single line to paste into a Command Prompt
opened **as administrator**:

```
netsh advfirewall firewall add rule name="Car Service Invoicing" dir=in action=allow protocol=TCP localport=8000 profile=private
```

### All four look fine and it still will not connect

Then the Wi-Fi itself is keeping devices apart. Two common causes:

- **The tablet is on the guest network** and the PC is on the main one, or
  the other way round. They have different names; check they match.
- **Client isolation** is switched on in the router — a setting that stops
  devices on the Wi-Fi from seeing each other at all. It is often on by
  default in business routers and in some mobile hotspots. Whoever manages
  the router can turn it off for the main network.

Also worth ruling out: the tablet is on mobile data rather than Wi-Fi.

---

## Who can get in

Everyone on that network. There is no login, no password, and no record of
who changed what.

**What to do about it, in order of how well it works:**

1. **Put customers on a separate guest network.** Most routers can do this
   and it costs nothing. The workshop's own devices stay on the main
   network, customers get the guest one, and the two cannot see each other.
   This is the right fix.
2. **Use a Wi-Fi password only staff know**, and change it when somebody
   leaves. Weaker, because anyone who has ever been told it keeps access.
3. **Ask for a passcode screen to be added to the application.** About an
   hour's work. Worth doing if the first option is not available.

**What not to do:** do not forward port 8000 on the router to make this
reachable from outside the workshop. That puts an application with no
password on the open internet, where it will be found within hours. If
somebody genuinely needs to use it from home, the answer is a VPN into the
workshop network, set up by whoever manages the router — not a hole in it.

---

## Reference

| | |
| --- | --- |
| On the PC itself | `http://localhost:8000` |
| From another device | `http://<the PC's address>:8000` |
| Serve this computer only | `run.bat` |
| Serve the local network | `network.bat` |
| Diagnose a connection | `check-network.bat` |
| Change the port | `set CARSERVICE_PORT=8001` before running |

The PC must be switched on and the application running. There is no service
running in the background — closing the black window stops it for everybody.
