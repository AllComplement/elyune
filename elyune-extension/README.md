# elyune

A production-ready screen recording browser extension built with WXT, React, and TypeScript. Features modern offscreen recording with automatic fallback for universal compatibility.

## Features

- 🎬 **Dual-Mode Recording**
  - Modern offscreen document API (Chrome 109+) - hidden, seamless recording
  - Automatic fallback to pinned tab recorder for older browsers

- 💾 **Smart Storage Management**
  - IndexedDB storage for large recordings
  - Storage quota monitoring prevents crashes
  - Chunked recording (1-second intervals) for reliability

- 🎨 **Quality Options**
  - Configurable resolutions (480p, 720p, 1080p, 4K)
  - Automatic codec selection (VP9 → VP8 → H264 fallback)
  - Adjustable bitrates for optimal file sizes

- ⌨️ **Keyboard Shortcuts**
  - `Alt+Shift+R` (Mac: `Command+Shift+R`) - Start recording
  - `Alt+Shift+S` (Mac: `Command+Shift+S`) - Stop recording
  - `Alt+Shift+P` (Mac: `Command+Shift+P`) - Pause/Resume

- 🔒 **Production-Ready**
  - Resource cleanup (streams, URLs, storage)
  - User-initiated stop detection
  - Professional error handling
  - State persistence across popup closes

## Installation

### For Development

1. **Clone the repository:**
   ```bash
   git clone git@github.com:AllComplement/elyune-extension.git
   cd elyune-extension
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development mode:**
   ```bash
   npm run dev          # Chrome (default)
   npm run dev:firefox  # Firefox
   ```

4. **Load in Chrome:**
   - Open `chrome://extensions`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `.output/chrome-mv3` directory

### For Production

1. **Build the extension:**
   ```bash
   npm run build            # Chrome
   npm run build:firefox    # Firefox
   ```

2. **Create distribution package:**
   ```bash
   npm run zip              # Chrome
   npm run zip:firefox      # Firefox
   ```

## Usage

### Recording Your Screen

1. Click the extension icon in your browser toolbar
2. Click "Start Recording"
3. Select the screen, window, or tab you want to record
4. Perform your recording
5. Click "Stop Recording" or use the keyboard shortcut
6. The video will be saved automatically as a `.webm` file

### Using Keyboard Shortcuts

- **Start:** Press `Alt+Shift+R` (or `Command+Shift+R` on Mac)
- **Stop:** Press `Alt+Shift+S` (or `Command+Shift+S` on Mac)
- **Pause/Resume:** Press `Alt+Shift+P` (or `Command+Shift+P` on Mac)

### Recording Modes

The extension automatically uses the best available recording method:

- **Offscreen Mode (Chrome 109+):** Hidden background recording with no visible UI
- **Tab Mode (Fallback):** Visible pinned tab with recording indicator for older browsers

## Architecture

### Project Structure

```
elyune-extension/
├── entrypoints/
│   ├── background.ts                    # Service worker orchestration
│   ├── content.ts                       # Content script (optional)
│   ├── offscreen-recorder/
│   │   ├── index.html                   # Offscreen document shell
│   │   └── index.ts                     # Modern recording implementation
│   ├── recorder/
│   │   ├── index.html                   # Tab recorder UI
│   │   └── index.ts                     # Fallback recording implementation
│   └── popup/
│       ├── App.tsx                      # Recording controls UI
│       ├── App.css                      # Popup styling
│       ├── index.html                   # Popup HTML
│       └── main.tsx                     # React entry point
├── types/
│   └── chrome.d.ts                      # Chrome API type definitions
├── wxt.config.ts                        # WXT configuration & manifest
├── tsconfig.json                        # TypeScript configuration
└── package.json                         # Dependencies & scripts
```

### Key Technologies

- **[WXT](https://wxt.dev)** - Web Extension Tools framework
- **[React](https://react.dev)** - UI library for popup interface
- **[TypeScript](https://www.typescriptlang.org/)** - Type safety
- **[localforage](https://localforage.github.io/localForage/)** - IndexedDB storage wrapper
- **Chrome Extension APIs** - offscreen, desktopCapture, downloads

## Development

### Available Scripts

```bash
npm run dev              # Start Chrome development server
npm run dev:firefox      # Start Firefox development server
npm run build            # Build for Chrome production
npm run build:firefox    # Build for Firefox production
npm run zip              # Create Chrome distribution zip
npm run zip:firefox      # Create Firefox distribution zip
npm run compile          # TypeScript type checking
```

### Development Workflow

1. Make changes to source files
2. Extension auto-reloads in development mode
3. Test functionality in browser
4. Check console for errors (background worker & popup)
5. Run `npm run compile` to verify TypeScript

### Debugging

**Background Service Worker:**
- Open `chrome://extensions`
- Find your extension
- Click "service worker" link
- Console shows background logs and offscreen recorder logs

**Popup:**
- Right-click extension icon → "Inspect popup"
- Console shows popup component logs

**Storage:**
```javascript
// Check stored state
await chrome.storage.local.get().then(console.log);

// Check IndexedDB chunks
const chunksStore = localforage.createInstance({ name: 'chunks' });
const keys = await chunksStore.keys();
console.log('Stored chunks:', keys);
```

## Technical Details

### Recording Flow

```
User clicks "Start Recording"
         ↓
Background worker receives message
         ↓
Try: Create offscreen document (Chrome 109+)
         ↓
    Success → Use getDisplayMedia() in offscreen
         ↓
    Failed → Create pinned recorder tab (fallback)
         ↓
Prompt user for screen/window selection
         ↓
MediaRecorder captures stream with quality settings
         ↓
Save chunks to IndexedDB with storage monitoring
         ↓
On stop: Collect chunks, create blob, download
         ↓
Cleanup: Stop streams, clear storage, revoke URLs
```

### Storage Strategy

- **Offscreen Mode:** IndexedDB via localforage (handles large recordings)
- **Tab Mode:** In-memory chunks (simpler fallback)
- **Monitoring:** Checks available quota every 5 seconds
- **Headroom:** Maintains 25MB minimum free space

### Quality Presets

| Quality | Resolution  | Video Bitrate | Audio Bitrate |
|---------|-------------|---------------|---------------|
| 480p    | 854 × 480   | 3 Mbps        | 96 kbps       |
| 720p    | 1280 × 720  | 5 Mbps        | 128 kbps      |
| 1080p   | 1920 × 1080 | 8 Mbps        | 128 kbps      |
| 4K      | 4096 × 2160 | 20 Mbps       | 192 kbps      |

Default: 1080p @ 30 FPS

### Codec Support

Automatic fallback chain:
1. VP9 with Opus (best compression)
2. VP8 with Opus (wider compatibility)
3. H264 (legacy fallback)
4. WebM (basic fallback)

## Permissions

### Required Permissions
- `tabs` - Access active tab for recording
- `activeTab` - Get current tab information
- `storage` - Save recording state
- `unlimitedStorage` - Store large video files
- `downloads` - Save recordings via download manager
- `tabCapture` - Capture tab content
- `system.display` - Get display information

### Optional Permissions
- `offscreen` - Modern offscreen recording (requested at runtime)
- `desktopCapture` - Fallback screen capture (requested at runtime)

## Browser Compatibility

- **Chrome 109+:** Full offscreen recording support
- **Chrome 100-108:** Tab-based fallback recording
- **Chromium-based browsers:** Edge, Brave, Opera (tab fallback)
- **Firefox:** Future support planned

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

Built with patterns from professional extensions like [Screenity](https://github.com/alyssaxuu/screenity).

## Support

For issues and feature requests, please [create an issue](https://github.com/AllComplement/elyune-extension/issues).
