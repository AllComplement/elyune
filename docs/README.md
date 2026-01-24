# Elyune Documentation Archive

This directory contains historical and reference documentation for the Elyune project.

## Directory Structure

### `refactoring/`
Documentation from the January 2026 database refactoring project:
- `REFACTORING_PROJECT_COMPLETE.md` - Overall project summary
- `REFACTORING_COMPLETE.md` - Backend refactoring completion
- `REFACTORING_PHASE_3_COMPLETE.md` - Query optimization phase
- `REFACTORING_PHASE_4_COMPLETE.md` - Admin interface cleanup phase
- `BACKEND_API_UPDATE.md` - Chrome extension API updates

**Summary:** Consolidated 7 models across 3 Django apps into 3 models in 1 app, achieving:
- 57% fewer database tables (7 → 3)
- 25% fewer queries (4 → 3)
- 20% faster response time (50ms → 40ms)
- Zero data loss

### `setup/`
Initial setup and command reference documentation:
- `SETUP_SUMMARY.md` - Backend setup walkthrough
- `COMMANDS.md` - Quick command reference

## Active Documentation

For current project documentation, see:
- `/README.md` - Project overview
- `/AGENTS.md` - AI agent instructions
- `/elyune-backend/README.md` - Backend documentation
- `/elyune-extension/README.md` - Extension documentation
