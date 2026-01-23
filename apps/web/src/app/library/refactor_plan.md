# Library Refactor Plan

## Phase 1: Atomic Component Extraction
Refactor the monolithic `page.tsx` into small, presentational components co-located in `apps/web/src/app/library/components/`.

- [x] **LibraryStats.tsx**: Display library statistics (Total, Downloaded, Converted, In Progress).
- [x] **LibraryPagination.tsx**: Extract the `PaginationControls` component.
- [x] **LibrarySelectionBar.tsx**: The toolbar for batch actions (Select All, Download, Convert, Delete) when items are selected.
- [x] **LibraryTabs.tsx**: The toggle between "Audiobooks" and "Podcasts".
- [x] **LibraryBooks.tsx**: The grid/list layout for displaying books.
- [x] **LibraryLocalItems.tsx**: The grid/list layout for displaying local items.
- [x] **LibraryEmptyState.tsx**: The various empty states (loading, no results, no local items).
- [x] **LibraryLocalPreview.tsx**: The "Local-only" preview section when viewing "All".

## Phase 2: Logic Separation (Orchestration)
Move the heavy state management, URL syncing, and data fetching out of `page.tsx`.

- [x] **hooks/useLibraryUrlParams.ts**:
    - Manage URL search parameters (search, status, content_type, series, source, sort, page).
    - Provide typed setters for these params.
    - Handle URL updates and router pushes.
- [x] **hooks/useLibraryData.ts**:
    - Encapsulate data fetching for Books, Local Items, Series Options, and Stats.
    - Handle the logic for "All" vs "Local" vs "Audible" data sources.
- [x] **hooks/useLibrarySelection.ts**:
    - Wrapper around `useUIStore` for selection mode.
    - Handle "Select All Page" and "Clear Selection".
- [x] **hooks/useLibraryActions.ts**:
    - Encapsulate mutation logic (Sync, Download, Convert, Delete, Repair).
    - Handle toast notifications for these actions.

## Phase 3: Layout Composition
Reassemble `page.tsx` to be a thin wrapper that passes data to a container component.

- [x] **LibraryContainer.tsx** (The Orchestrator):
    - Uses the custom hooks to fetch data and state.
    - Renders the layout using the atomic components.
- [x] **page.tsx**:
    - Simply renders `<LibraryContainer />`.