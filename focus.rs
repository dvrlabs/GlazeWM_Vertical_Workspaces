// focus.rs
//
// Fire-and-forget UDP trigger for the GlazeWM focus daemon.
// Sends the first CLI argument (e.g. "up" or "down") as a UDP
// packet to 127.0.0.1:7744, then exits.
//
//
// Build:
//   rustc -O -C debuginfo=0 -C link-arg=/DEBUG:NONE focus.rs
//
// Smallest possible:
//   rustc -O -C opt-level=z -C strip=symbols -C debuginfo=0 -C link-arg=/DEBUG:NONE focus.rs
//
//
// The #![windows_subsystem = "windows"] attribute below prevents
// a console window from flashing on each invocation when called
// from GlazeWM's shell-exec.

#![windows_subsystem = "windows"]

use std::net::UdpSocket;

fn main() {
    let arg = std::env::args().nth(1).unwrap_or_default();
    let sock = UdpSocket::bind("127.0.0.1:0").unwrap();
    sock.send_to(arg.as_bytes(), "127.0.0.1:7744").unwrap();
}
