import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    permissions: [
      'tabs',
      'activeTab',
      'storage',
      'unlimitedStorage',
      'downloads',
      'tabCapture',
      'system.display',
      'offscreen',
      'microphone'
    ],
    commands: {
      'start-recording': {
        suggested_key: {
          default: 'Alt+Shift+R',
          mac: 'Command+Shift+R',
        },
        description: 'Start recording',
      },
      'stop-recording': {
        suggested_key: {
          default: 'Alt+Shift+S',
          mac: 'Command+Shift+S',
        },
        description: 'Stop recording',
      },
      'pause-recording': {
        suggested_key: {
          default: 'Alt+Shift+P',
          mac: 'Command+Shift+P',
        },
        description: 'Pause/Resume recording',
      },
    },
  },
});
