# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes        |
| < 0.1   | no         |

## Reporting a Vulnerability

If you believe you have found a security vulnerability in ROBIN-FPGA, please **do not** open a public issue. Instead, email **selsayed@seas.upenn.edu** with:

1. A description of the issue and its potential impact.
2. Steps to reproduce, including a minimal example if possible.
3. Affected version(s).
4. Suggested mitigation if you have one.

You will receive a response within 5 business days acknowledging the report. We will then work with you on a coordinated disclosure timeline, typically 90 days, before public disclosure.

## Scope

Security issues we consider in scope:
- Arbitrary code execution via maliciously-crafted configuration or checkpoint files
- Path traversal in the toolchain wrapper
- Insecure deserialisation of trained policy checkpoints
- Audit-trail tampering vulnerabilities

Out of scope:
- Bugs in third-party dependencies (please report upstream)
- Issues requiring physical access to the training machine
- Denial-of-service via resource exhaustion in research-grade code
