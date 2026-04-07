# Documentation Index

This index is intentionally explicit so implementation, operations, and troubleshooting paths are easy to verify.

## Start Here

1. [README](../README.md)
2. [Architecture](./ARCHITECTURE.md)
3. [UX Spec](./UX_SPEC.md)
4. [Launchers](./LAUNCHERS.md)

## Runtime and Design

- [Architecture](./ARCHITECTURE.md)
  - Layer A shell responsibilities
  - Layer B bridge responsibilities
  - stage routing and artifact boundaries
- [Project Structure](./PROJECT_STRUCTURE.md)
  - directory ownership and expected contents
- [Self-Containment Limitations](./SELF_CONTAINMENT_LIMITATIONS.md)
  - explicit external dependencies and non-goals

## User Workflow and UX

- [UX Spec](./UX_SPEC.md)
  - deep-run mode prompt
  - MOE vs single-Gemma behavior
  - run summary and fallback expectations

## Launch and Setup

- [Launchers](./LAUNCHERS.md)
  - `scripts/launch.js` behavior and launch-plan checks
  - macOS and Windows wrapper behavior
- [macOS Setup](./MACOS_SETUP.md)
- [Windows Setup](./WINDOWS_SETUP.md)

## Operations and Recovery

- [Troubleshooting](./TROUBLESHOOTING.md)
  - Gemma diagnostics lanes
  - empty-response/degraded fallback interpretation
  - bridge and parser recovery paths

## Additional References

- Bridge reference: [src/bridge/python/BRIDGE_README.md](../src/bridge/python/BRIDGE_README.md)
- Audits: `../audits/`
- Reports: `../reports/`
- Tests: `../tests/`
