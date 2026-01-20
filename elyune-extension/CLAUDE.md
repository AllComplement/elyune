# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Browser extension built with WXT (Web Extension Tools) and React for cross-browser compatibility.

## Development Commands

```bash
# Development
npm run dev              # Chrome (default)
npm run dev:firefox      # Firefox

# Build
npm run build            # Chrome
npm run build:firefox    # Firefox

# Distribution
npm run zip              # Create Chrome zip
npm run zip:firefox      # Create Firefox zip

# Type checking
npm run compile          # Run TypeScript without emitting
```

## Architecture

### Entry Points (`entrypoints/`)

WXT uses file-based entry points:

- **`background.ts`**: Service worker running in extension context (uses `defineBackground()`)
- **`content.ts`**: Script injected into web pages (uses `defineContentScript()` with `matches` array)
- **`popup/`**: React-based popup UI with standard React setup

Content scripts require URL match patterns in the `matches` array to specify where they inject.

### Configuration

- **`wxt.config.ts`**: Enables React module via `@wxt-dev/module-react`
- **`tsconfig.json`**: Extends `.wxt/tsconfig.json` with React JSX support

The `browser` API is globally available for extension functionality.
