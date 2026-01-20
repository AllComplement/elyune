// Add Chrome-specific types that aren't in the standard definitions
declare namespace chrome {
  namespace offscreen {
    enum Reason {
      USER_MEDIA = 'USER_MEDIA',
      DISPLAY_MEDIA = 'DISPLAY_MEDIA',
      AUDIO_PLAYBACK = 'AUDIO_PLAYBACK',
    }

    function createDocument(options: {
      url: string;
      reasons: Reason[];
      justification: string;
    }): Promise<void>;

    function closeDocument(): Promise<void>;
  }

  namespace runtime {
    enum ContextType {
      OFFSCREEN_DOCUMENT = 'OFFSCREEN_DOCUMENT',
    }

    function getContexts(filter: {
      contextTypes: ContextType[];
    }): Promise<Array<{ documentUrl?: string }>>;
  }

  namespace downloads {
    function download(options: {
      url: string;
      filename: string;
      saveAs?: boolean;
    }): Promise<number>;

    interface DownloadDelta {
      id: number;
      state?: {
        previous?: string;
        current?: string;
      };
      error?: {
        previous?: string;
        current?: string;
      };
      bytesReceived?: {
        previous?: number;
        current?: number;
      };
    }

    namespace onChanged {
      function addListener(callback: (delta: DownloadDelta) => void): void;
      function removeListener(callback: (delta: DownloadDelta) => void): void;
    }
  }
}
