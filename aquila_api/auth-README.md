# OIDC identity boundary

`auth.py` maps verified Authentik/OIDC claims to Legion's canonical `Principal` model. It enforces issuer, audience, subject, group-shape, and workload-vs-human rules, then maps only configured groups to roles.

The module does not verify JWT signatures or call Authentik. A production HTTP adapter must inject a verifier that validates signature, issuer, audience, expiry, and key rotation before calling `AuthentikPrincipalMapper`.
