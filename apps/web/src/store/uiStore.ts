/**
 * UI Store
 * Zustand store for UI state management
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { safeLocalStorage } from "@/lib/utils";

/**
 * View mode for book display
 */
export type ViewMode = "grid" | "list";

/**
 * Sidebar state
 */
export interface SidebarState {
  isOpen: boolean;
  isCollapsed: boolean;
}

/**
 * Drawer state for mobile
 */
export interface DrawerState {
  isOpen: boolean;
  content: "sidebar" | "player" | "settings" | null;
}

/**
 * Modal state
 */
export interface ModalState {
  isOpen: boolean;
  type: "settings" | "bookDetails" | "jobDetails" | "confirm" | null;
  data: Record<string, unknown> | null;
}

/**
 * Toast notification
 */
export interface Toast {
  id: string;
  type: "success" | "error" | "warning" | "info";
  title: string;
  message?: string;
  duration?: number;
}

/**
 * UI state interface
 */
export interface UIState {
  // View settings
  viewMode: ViewMode;

  // Sidebar state
  sidebar: SidebarState;

  // Drawer state (mobile)
  drawer: DrawerState;

  // Modal state
  modal: ModalState;

  // Selection state
  selectedBooks: Set<string>;
  isSelectionMode: boolean;

  // Job Drawer state
  isJobDrawerOpen: boolean;

  // Library UI
  isRepairProgressCardVisible: boolean;

  // Progress Popover state
  progressPopover: {
    isOpen: boolean;
    isMinimized: boolean;
    position: { x: number; y: number };
    activeTab: "active" | "failed" | "history";
    /**
     * UI-only "clear" marker used by ProgressPopover. Hides failed/history rows
     * created before this timestamp without deleting anything from the backend.
     */
    clearedBeforeMs: number;
  };

  // Toasts
  toasts: Toast[];

  // Search
  searchQuery: string;
  isSearchOpen: boolean;

  // Loading states
  isGlobalLoading: boolean;
}

/**
 * UI actions interface
 */
export interface UIActions {
  // View mode
  setViewMode: (mode: ViewMode) => void;
  toggleViewMode: () => void;

  // Sidebar
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  collapseSidebar: () => void;
  expandSidebar: () => void;

  // Drawer
  openDrawer: (content: DrawerState["content"]) => void;
  closeDrawer: () => void;

  // Modal
  openModal: (type: ModalState["type"], data?: Record<string, unknown> | null) => void;
  closeModal: () => void;

  // Selection
  selectBook: (asin: string) => void;
  deselectBook: (asin: string) => void;
  toggleBookSelection: (asin: string) => void;
  selectAllBooks: (asins: string[]) => void;
  clearSelection: () => void;
  setSelectionMode: (enabled: boolean) => void;

  // Job Drawer
  setJobDrawerOpen: (open: boolean) => void;

  // Library UI
  setRepairProgressCardVisible: (visible: boolean) => void;
  toggleRepairProgressCardVisible: () => void;

  // Progress Popover
  openProgressPopover: (tab?: UIState["progressPopover"]["activeTab"]) => void;
  closeProgressPopover: () => void;
  toggleProgressPopover: () => void;
  minimizeProgressPopover: () => void;
  maximizeProgressPopover: () => void;
  updateProgressPopoverPosition: (x: number, y: number) => void;
  setProgressPopoverTab: (tab: UIState["progressPopover"]["activeTab"]) => void;
  clearProgressPopoverUI: () => void;

  // Toasts
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
  clearToasts: () => void;

  // Search
  setSearchQuery: (query: string) => void;
  openSearch: () => void;
  closeSearch: () => void;
  toggleSearch: () => void;

  // Loading
  setGlobalLoading: (loading: boolean) => void;
}

export type UIStore = UIState & UIActions;

/**
 * Generate unique toast ID
 */
function generateToastId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * UI store with persistence for view preferences
 */
export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      // Initial state
      viewMode: "grid",
      sidebar: { isOpen: true, isCollapsed: false },
      drawer: { isOpen: false, content: null },
      modal: { isOpen: false, type: null, data: null },
      isJobDrawerOpen: false,
      isRepairProgressCardVisible: true,
      progressPopover: {
        isOpen: false,
        isMinimized: false,
        position: { x: 20, y: 80 },
        activeTab: "active",
        clearedBeforeMs: 0,
      },
      selectedBooks: new Set<string>(),
      isSelectionMode: false,
      toasts: [],
      searchQuery: "",
      isSearchOpen: false,
      isGlobalLoading: false,

      // View mode
      setViewMode: (mode: ViewMode) => set({ viewMode: mode }),
      toggleViewMode: () =>
        set((state) => ({
          viewMode: state.viewMode === "grid" ? "list" : "grid",
        })),

      // Sidebar
      openSidebar: () =>
        set((state) => ({
          sidebar: { ...state.sidebar, isOpen: true },
        })),
      closeSidebar: () =>
        set((state) => ({
          sidebar: { ...state.sidebar, isOpen: false },
        })),
      toggleSidebar: () =>
        set((state) => ({
          sidebar: { ...state.sidebar, isOpen: !state.sidebar.isOpen },
        })),
      collapseSidebar: () =>
        set((state) => ({
          sidebar: { ...state.sidebar, isCollapsed: true },
        })),
      expandSidebar: () =>
        set((state) => ({
          sidebar: { ...state.sidebar, isCollapsed: false },
        })),

      // Drawer
      openDrawer: (content) => set({ drawer: { isOpen: true, content } }),
      closeDrawer: () => set({ drawer: { isOpen: false, content: null } }),

      // Modal
      openModal: (type, data = null) =>
        set({ modal: { isOpen: true, type, data } }),
      closeModal: () => set({ modal: { isOpen: false, type: null, data: null } }),

      // Selection
      selectBook: (asin) =>
        set((state) => {
          const newSelection = new Set(state.selectedBooks);
          newSelection.add(asin);
          return { selectedBooks: newSelection };
        }),
      deselectBook: (asin) =>
        set((state) => {
          const newSelection = new Set(state.selectedBooks);
          newSelection.delete(asin);
          return {
            selectedBooks: newSelection,
            isSelectionMode:
              newSelection.size > 0 ? state.isSelectionMode : false,
          };
        }),
      toggleBookSelection: (asin) => {
        const { selectedBooks, selectBook, deselectBook } = get();
        if (selectedBooks.has(asin)) {
          deselectBook(asin);
        } else {
          selectBook(asin);
        }
      },
      selectAllBooks: (asins) =>
        set({
          selectedBooks: new Set(asins),
          isSelectionMode: asins.length > 0,
        }),
      clearSelection: () =>
        set({
          selectedBooks: new Set<string>(),
          isSelectionMode: false,
        }),
      setSelectionMode: (enabled) =>
        set((state) => ({
          isSelectionMode: enabled,
          selectedBooks: enabled ? state.selectedBooks : new Set<string>(),
        })),

      // Job Drawer
      setJobDrawerOpen: (open) => set({ isJobDrawerOpen: open }),

      // Library UI
      setRepairProgressCardVisible: (visible) => set({ isRepairProgressCardVisible: visible }),
      toggleRepairProgressCardVisible: () =>
        set((state) => ({ isRepairProgressCardVisible: !state.isRepairProgressCardVisible })),

      // Progress Popover
      openProgressPopover: (tab) =>
        set((state) => ({
          progressPopover: {
            ...state.progressPopover,
            isOpen: true,
            isMinimized: false,
            activeTab: tab ?? state.progressPopover.activeTab,
          },
        })),
      closeProgressPopover: () =>
        set((state) => ({
          progressPopover: { ...state.progressPopover, isOpen: false },
        })),
      toggleProgressPopover: () =>
        set((state) => ({
          progressPopover: {
            ...state.progressPopover,
            isOpen: !state.progressPopover.isOpen,
            isMinimized: false, // Always unminimize on toggle if opening
          },
        })),
      minimizeProgressPopover: () =>
        set((state) => ({
          progressPopover: { ...state.progressPopover, isMinimized: true },
        })),
      maximizeProgressPopover: () =>
        set((state) => ({
          progressPopover: { ...state.progressPopover, isMinimized: false },
        })),
      updateProgressPopoverPosition: (x, y) =>
        set((state) => ({
          progressPopover: { ...state.progressPopover, position: { x, y } },
        })),
      setProgressPopoverTab: (tab) =>
        set((state) => ({
          progressPopover: { ...state.progressPopover, activeTab: tab },
        })),
      clearProgressPopoverUI: () =>
        set((state) => ({
          progressPopover: {
            ...state.progressPopover,
            activeTab: "active",
            clearedBeforeMs: Date.now(),
          },
        })),

      // Toasts
      addToast: (toast) => {
        const id = generateToastId();
        const newToast: Toast = { ...toast, id };

        set((state) => ({
          toasts: [...state.toasts, newToast],
        }));

        // Auto-remove after duration
        const duration = toast.duration ?? 5000;
        if (duration > 0) {
          setTimeout(() => {
            get().removeToast(id);
          }, duration);
        }
      },
      removeToast: (id) =>
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        })),
      clearToasts: () => set({ toasts: [] }),

      // Search
      setSearchQuery: (query) => set({ searchQuery: query }),
      openSearch: () => set({ isSearchOpen: true }),
      closeSearch: () => set({ isSearchOpen: false, searchQuery: "" }),
      toggleSearch: () =>
        set((state) => ({
          isSearchOpen: !state.isSearchOpen,
          searchQuery: state.isSearchOpen ? "" : state.searchQuery,
        })),

      // Loading
      setGlobalLoading: (loading) => set({ isGlobalLoading: loading }),
    }),
    {
      name: "ui-storage",
      storage: createJSONStorage(() => safeLocalStorage),
      // Only persist view preferences
      partialize: (state) => ({
        viewMode: state.viewMode,
        sidebar: state.sidebar,
        isRepairProgressCardVisible: state.isRepairProgressCardVisible,
        progressPopover: {
          ...state.progressPopover,
          isOpen: false, // don't auto-open on reload
        },
      }),
    }
  )
);

/**
 * Selector hooks for common UI state
 */
export const useViewMode = () => useUIStore((state) => state.viewMode);

export const useSidebar = () => useUIStore((state) => state.sidebar);

export const useSelectedBooks = () => {
  const selectedBooks = useUIStore((state) => state.selectedBooks);
  const isSelectionMode = useUIStore((state) => state.isSelectionMode);
  return {
    selectedBooks: Array.from(selectedBooks),
    count: selectedBooks.size,
    isSelectionMode,
    hasSelection: selectedBooks.size > 0,
  };
};

export const useToasts = () => useUIStore((state) => state.toasts);

export const useSearch = () =>
  useUIStore((state) => ({
    query: state.searchQuery,
    isOpen: state.isSearchOpen,
  }));
