# GitHub Actions Workflows

This directory contains automated CI/CD workflows for the Elyune project.

## Workflows

### 1. CI - Build and Test Extension (`ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches (when extension files change)
- Pull requests to `main` or `develop` (when extension files change)

**What it does:**
- Builds extension for both Chrome and Firefox
- Runs TypeScript type checking
- Creates distribution zips
- Runs Playwright tests (Chrome only)
- Uploads build artifacts for 7 days

**Matrix strategy:** Builds both Chrome and Firefox versions in parallel

**Artifacts:**
- `elyune-chrome-{sha}` - Chrome build
- `elyune-firefox-{sha}` - Firefox build
- `playwright-report` - Test results (if tests run)

---

### 2. Release - Build Extension and Create Release (`release.yml`)

**Triggers:**
- Push tags matching `v*` (e.g., `v1.0.0`, `v1.2.3`)

**What it does:**
1. Builds extension for Chrome and Firefox
2. Runs type checking
3. Creates distribution zips
4. Generates changelog from git commits
5. Creates GitHub Release with:
   - Release notes with installation instructions
   - Chrome zip file
   - Firefox zip file
6. Uploads artifacts for 90 days

**Release artifacts:**
- `elyune-chrome-v{version}.zip` - Chrome extension
- `elyune-firefox-v{version}.zip` - Firefox extension

---

## Creating a Release

### Option 1: Using Git Tags (Recommended)

```bash
# 1. Update version in package.json
cd elyune-extension
npm version patch  # or minor, major
# This updates package.json and creates a git tag

# 2. Push the tag
git push origin v1.0.0

# GitHub Actions will automatically:
# - Build the extension
# - Create a GitHub Release
# - Attach zip files
```

### Option 2: Manual Tag Creation

```bash
# 1. Create and push tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 2. The workflow will trigger automatically
```

### Option 3: Using GitHub CLI

```bash
# Create a release directly
gh release create v1.0.0 \
  --title "Elyune v1.0.0" \
  --notes "Release notes here"

# Or let the workflow handle it by just pushing the tag
git tag v1.0.0
git push origin v1.0.0
```

---

## Release Notes Format

The release workflow automatically generates release notes including:

- **What's Changed**: List of commits since last release
- **Installation Instructions**: For both Chrome and Firefox
- **Backend Setup**: Instructions for running the backend
- **Links**: To README and documentation

Example output:
```markdown
## What's Changed

- feat(extension): add duration display (abc123)
- fix(backend): correct serializer field mapping (def456)
- refactor(extension): optimize layout (ghi789)

## Installation

### Chrome/Edge
1. Download `elyune-chrome-v1.0.0.zip`
2. Unzip the file
...
```

---

## Workflow Permissions

Both workflows require:
- **Read**: Repository contents
- **Write**: For creating releases (release.yml only)

These are configured in the workflow files:
```yaml
permissions:
  contents: write  # Required for creating releases
```

---

## Artifacts Retention

- **CI builds**: 7 days
- **Release builds**: 90 days
- **Test reports**: 7 days

Artifacts can be downloaded from:
- Workflow run page (Actions tab)
- GitHub Release page (for releases)

---

## Local Testing

Before pushing a tag, test the build locally:

```bash
cd elyune-extension

# Install dependencies
npm ci

# Type check
npm run compile

# Build Chrome
npm run build
npm run zip

# Build Firefox
npm run build:firefox
npm run zip:firefox

# Run tests
npm run test

# Verify outputs
ls -lh .output/
```

---

## Troubleshooting

### Build fails with "npm ci" error
**Solution**: Ensure `package-lock.json` is committed and up-to-date
```bash
npm install
git add package-lock.json
git commit -m "chore: update package-lock.json"
```

### Type check fails
**Solution**: Fix TypeScript errors locally first
```bash
npm run compile
# Fix any errors shown
```

### Tests fail
**Solution**: Run tests locally to debug
```bash
npm run test
npm run test:ui  # Opens Playwright UI for debugging
```

### Release not created
**Solution**: Check workflow logs in Actions tab
- Verify tag format matches `v*`
- Check for build errors
- Ensure GITHUB_TOKEN has proper permissions

### Wrong version in release
**Solution**: Ensure tag matches version in package.json
```bash
# Tag should be v1.0.0 if package.json has "version": "1.0.0"
git tag -d v1.0.0  # Delete wrong tag locally
git push origin :v1.0.0  # Delete from remote
git tag v1.0.0  # Create correct tag
git push origin v1.0.0
```

---

## Advanced: Prerelease

To create a prerelease (beta, alpha, rc):

```bash
# 1. Create prerelease tag
git tag -a v1.0.0-beta.1 -m "Beta release 1.0.0-beta.1"
git push origin v1.0.0-beta.1

# 2. Modify release.yml to detect prerelease
# Add to the workflow:
# prerelease: ${{ contains(github.ref, 'beta') || contains(github.ref, 'alpha') || contains(github.ref, 'rc') }}
```

---

## Monitoring

### View Workflow Status

```bash
# Using GitHub CLI
gh workflow list
gh run list --workflow=release.yml
gh run view {run-id}

# Or visit:
# https://github.com/AllComplement/elyune/actions
```

### Download Artifacts

```bash
# Using GitHub CLI
gh run download {run-id}

# Or manually from Actions tab
```

---

## Best Practices

1. **Always test locally** before creating a release tag
2. **Use semantic versioning**: `v{major}.{minor}.{patch}`
3. **Update CHANGELOG.md** before releases (optional, but recommended)
4. **Review release notes** before publishing
5. **Test the release zips** after creation
6. **Keep package.json version in sync** with git tags

---

## Extending the Workflows

### Add Backend Tests

To add backend tests to CI:

```yaml
# Add to ci.yml
backend-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: docker compose -f elyune-backend/docker-compose.yml run web python manage.py test
```

### Add Code Quality Checks

```yaml
# Add to ci.yml
code-quality:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: npm ci
    - run: npx eslint .  # If ESLint is configured
```

### Add Automated Store Submission

For Chrome Web Store:
```yaml
# Add to release.yml after build
- name: Submit to Chrome Web Store
  uses: trmcnvn/chrome-addon@v2
  with:
    extension: 'chrome-extension-id'
    zip: 'elyune-chrome-v${{ steps.get_version.outputs.VERSION }}.zip'
    client-id: ${{ secrets.CHROME_CLIENT_ID }}
    client-secret: ${{ secrets.CHROME_CLIENT_SECRET }}
    refresh-token: ${{ secrets.CHROME_REFRESH_TOKEN }}
```

---

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [WXT Build Documentation](https://wxt.dev/guide/essentials/building.html)
- [Chrome Extension Publishing](https://developer.chrome.com/docs/webstore/publish/)
- [Firefox Add-on Publishing](https://extensionworkshop.com/documentation/publish/)
