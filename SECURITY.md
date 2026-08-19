# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in `os-manager`, please do not open a public issue.

Report security issues directly to the maintainers via email at `security@os-manager.dev` or through private GitHub Security Advisories.

We review incoming vulnerability reports within 48 hours and release patched versions promptly.

## Security Invariants

The `os-manager` control plane enforces strict safety invariants:

1. **Root Protection**: Commands executing root obliteration (`rm -rf /`) or home directory deletion are hard-blocked.
2. **Lifecycle Safeguards**: Destructive WSL unregistration commands (`wsl --unregister`) are blocked deterministically.
3. **Container Sandboxing**: Untrusted subagent execution occurs within rootless container wrappers with read-only root filesystems.
