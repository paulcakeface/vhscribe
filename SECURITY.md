# Security policy

## Supported versions

| Version | Security updates |
| --- | --- |
| 0.1.x | Supported |
| Earlier/unreleased snapshots | Not supported |

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** private-reporting feature when it is enabled for the
repository. If it is unavailable, contact the maintainer privately through the contact method on
their GitHub profile. Do not open a public issue for an unpatched vulnerability and do not attach
recordings, `.env` files, tokens, private paths, or LAN details.

Include the affected version/commit, impact, reproduction steps using synthetic input where
possible, and any proposed mitigation. You should receive an acknowledgement within seven days;
the fix timeline depends on severity and maintainer availability.

## Deployment boundary

VHScribe 0.1.x has no application authentication, authorization, or TLS. It is intended for one
trusted host or a trusted private LAN. The safe default binds to loopback. Do not expose the HTTP,
WebRTC, RTSP, or MediaMTX API surfaces to the public internet. A reverse proxy alone does not make
the capture controls safe unless it supplies authentication, TLS, and appropriate network policy.

The Docker socket is not mounted, containers are not privileged, and only required capture devices
are mapped. Treat Docker access, the capture directory, and `.env` as privileged local assets.
