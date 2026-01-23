# Player UI & Experience Backlog

## Player Page (`/player`)

### Layout & Navigation
- [ ] **Relocate "Back to Library"**: Move the "Back to Library" button from the global header/title bar into the player container itself (upper-left corner). This keeps navigation context local to the player experience.
- [ ] **Responsive Layout Optimization**:
    - **Current State**: 2-column layout (Left: Cover + Chapters, Right: Controls).
    - **Goal**: Optimize for distinct viewports.
        - *Desktop*: Ensure balanced whitespace and vertical alignment. Consider if Cover/Chapters vs Controls is the best split or if Cover should be central.
        - *Mobile*: Stack order is critical. Ensure Cover -> Controls -> Chapters is the natural flow.

### Playback Controls
- [ ] **Fix Settings Button**: The settings button (equalizer/advanced audio) is currently dead code. Implement the modal/popover or hide it until ready.
- [ ] **Granular Speed Controls**:
    - Add finer increments (e.g., 0.1x steps) or a custom input.
    - [ ] **Fix Dropdown Styling**: The chevron icon in the speed selector is misaligned (too close to the right edge). Fix the CSS/Tailwind spacing.

### Metadata & Info
- [ ] **Extended Metadata View**: Add a feature/modal to view detailed book info that isn't currently shown:
    - Description (Synopsis)
    - Narrator(s)
    - Publisher
    - Technical Specs: Bitrate, Sample Rate, Format
    - ASIN
    - File Location (Local Path)

## StickyPlayer (Global Footer)

### Functional Overhaul (Major)
- [ ] **Wire Up API Integration**: The component currently appears to be a "dead container" or uses mock/outdated logic.
    - Connect `onPlayPause`, `onSeek`, `onSkip` to `usePlayerStore` actions.
    - Ensure it reflects the *actual* global player state (`isPlaying`, `currentTime`, `currentBook`).
- [ ] **Enterprise-Grade Polish**:
    - **Persistence**: Ensure it persists state/visibility correctly across page navigations.
    - **Synchronization**: It must sync perfectly with the main Player page (if the user pauses on the page, the sticky player must pause instantly, and vice versa).
    - **Error Handling**: Gracefully handle missing covers, stream errors, or loading states.

## Enterprise / Smart Player Features (The "Spotify-Killer" Tier)

### 1. Continuity & Handoff ("It Just Works")
- [ ] **Smart Resume**:
    - If the user hasn't listened for >24 hours (or a configurable threshold), automatically rewind 10-30 seconds upon resume to help them re-acquire context.
    - Display a subtle toast: "Rewound 20s for context."
- [ ] **Seamless Series Transition**:
    - When a book finishes (`progress >= 99%` or chapter end), query the API for the *next* book in the series.
    - If available locally, prompt: "Next in Series: [Title]. Play now?" (or auto-play if enabled).
- [ ] **Position Conflict Resolution**:
    - On load, if the local position differs significantly (>1m) from the server's `last_played` position (implying listening happened on another device), prompt the user: "Resume from [Time] (Server) or Keep [Time] (Local)?"

### 2. Native OS Integration
- [ ] **Media Session API**:
    - Fully integrate `navigator.mediaSession` to support hardware media keys (Play/Pause/Next/Prev) and OS-level lock screen controls.
    - Populate metadata (Title, Author, Album Art) so the OS "Now Playing" widget looks rich and native.
    - Handle "Action Handlers" for seeking and chapter skipping.

### 3. "Smart" Listening Features
- [ ] **Sleep Timer**:
    - Implement a timer dropdown (15m, 30m, 60m, End of Chapter).
    - *Smart Fade-out*: Gently lower volume over the last 60 seconds instead of a hard cut.
- [ ] **Silence Removal / Smart Speed** (Advanced):
    - Analyze the audio buffer (Web Audio API) to detect silence gaps and dynamically speed up `playbackRate` during them. (High complexity, high value).
- [ ] **Voice Boost / EQ**:
    - Simple 3-band EQ or a "Voice Boost" toggle (boost 1-4kHz range) for murky audiobooks.

### 4. Visual & Interaction Polish
- [ ] **Segmented Progress Bar**:
    - Instead of one long bar, visualize chapters as distinct segments on the timeline (like YouTube or Netflix).
    - Hovering a segment shows the Chapter Title.
- [ ] **Keyboard Shortcuts**:
    - Bind global hotkeys for desktop power users:
        - `Space`: Play/Pause
        - `Left/Right`: Seek -15s / +30s
        - `Up/Down`: Volume
        - `M`: Mute
        - `Shift + N`: Next Chapter
- [ ] **Mini-Player Transitions**:
    - Implement a shared layout animation (Framer Motion) so the specific book cover "flies" from the sticky player to the main player page (and back) for a cohesive app feel.

