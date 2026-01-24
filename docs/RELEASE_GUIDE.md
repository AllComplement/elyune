# 🚀 Creating a Release

Quick reference for creating Elyune extension releases.

## Prerequisites

✅ All changes committed and pushed to `main`  
✅ Extension builds successfully locally  
✅ Tests pass (`npm run test`)  
✅ Version updated in `elyune-extension/package.json`

---

## Method 1: Automatic (Recommended)

Use `npm version` to automatically update package.json and create a git tag:

```bash
cd elyune-extension

# For bug fixes (1.0.0 → 1.0.1)
npm version patch

# For new features (1.0.0 → 1.1.0)
npm version minor

# For breaking changes (1.0.0 → 2.0.0)
npm version major

# Push changes and tags
cd ..
git push && git push --tags
```

GitHub Actions will automatically:
- Build Chrome and Firefox versions
- Run tests
- Create GitHub Release
- Attach downloadable zip files

---

## Method 2: Manual Tag

```bash
# 1. Update version in package.json manually
cd elyune-extension
# Edit package.json: "version": "1.0.0"

# 2. Commit the version change
git add package.json
git commit -m "chore: bump version to 1.0.0"
git push

# 3. Create and push tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

---

## Method 3: GitHub CLI

```bash
# Create tag and let workflow create release
git tag v1.0.0
git push origin v1.0.0

# Or create release directly (workflow won't run)
gh release create v1.0.0 \
  --title "Elyune v1.0.0" \
  --generate-notes
```

---

## Pre-Release Checklist

Before creating a release tag:

```bash
cd elyune-extension

# 1. Install dependencies
npm ci

# 2. Type check
npm run compile

# 3. Build Chrome
npm run build

# 4. Build Firefox
npm run build:firefox

# 5. Run tests
npm run test

# 6. Check build sizes
ls -lh .output/chrome-mv3.zip
ls -lh .output/firefox-mv3.zip

# 7. Verify version matches
cat package.json | grep version
```

---

## Monitoring Release

### View Workflow Status

```bash
# Using GitHub CLI
gh run list --workflow=release.yml
gh run watch  # Watch latest run

# Or visit:
# https://github.com/AllComplement/elyune/actions/workflows/release.yml
```

### Download Release

```bash
# List releases
gh release list

# Download specific release
gh release download v1.0.0

# Or visit:
# https://github.com/AllComplement/elyune/releases
```

---

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **v1.0.0** → **v1.0.1**: Bug fixes (patch)
- **v1.0.0** → **v1.1.0**: New features (minor)
- **v1.0.0** → **v2.0.0**: Breaking changes (major)

**Pre-releases:**
- `v1.0.0-alpha.1`: Alpha version
- `v1.0.0-beta.1`: Beta version
- `v1.0.0-rc.1`: Release candidate

---

## Release Artifacts

Each release includes:

📦 **elyune-chrome-v{version}.zip**
- Chrome/Edge extension package
- Ready for Chrome Web Store submission
- Or manual installation

📦 **elyune-firefox-v{version}.zip**
- Firefox extension package
- For temporary loading in Firefox
- Needs Mozilla signing for production

---

## Troubleshooting

### Workflow didn't trigger
- Check tag format: Must be `v*` (e.g., `v1.0.0`, not `1.0.0`)
- Verify tag was pushed: `git push origin v1.0.0`

### Build failed
- Check Actions tab for error logs
- Run build locally first: `npm run build`
- Fix errors and create new tag (delete old one first)

### Wrong version in release
```bash
# Delete tag locally and remotely
git tag -d v1.0.0
git push origin :v1.0.0

# Delete release on GitHub
gh release delete v1.0.0

# Fix version and recreate
npm version 1.0.0
git push && git push --tags
```

---

## What Happens After Release

1. ✅ GitHub Release created with notes
2. ✅ Chrome and Firefox zips attached
3. ✅ Artifacts stored for 90 days
4. ✅ Release visible in Releases page
5. ✅ Users can download and install

**Next steps:**
- Test installation from release zips
- Submit to Chrome Web Store (manual)
- Submit to Firefox Add-ons (manual)
- Announce release to users

---

## Quick Commands

```bash
# Test build locally
npm run build && npm run test

# Create patch release
npm version patch && git push && git push --tags

# View release status
gh run list --workflow=release.yml

# Download latest release
gh release download

# Delete failed release
gh release delete v1.0.0 && git tag -d v1.0.0 && git push origin :v1.0.0
```

---

## Example Release Flow

```bash
# 1. Finish features and bug fixes
git commit -m "feat: add new recording feature"
git push

# 2. Test everything works
cd elyune-extension
npm run test

# 3. Create release (patch version)
npm version patch
# This updates package.json: 1.0.0 → 1.0.1
# And creates tag: v1.0.1

# 4. Push everything
cd ..
git push && git push --tags

# 5. Monitor workflow
gh run watch

# 6. Verify release created
gh release view v1.0.1

# 7. Download and test
gh release download v1.0.1
unzip elyune-chrome-v1.0.1.zip -d test-install
# Load in Chrome to test

# 8. Done! 🎉
```

---

For detailed information, see [.github/workflows/README.md](.github/workflows/README.md)
