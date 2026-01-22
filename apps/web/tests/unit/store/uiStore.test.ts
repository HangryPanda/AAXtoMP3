/**
 * UI Store Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useUIStore } from "@/store/uiStore";

describe("UI Store", () => {
  beforeEach(() => {
    // Reset store state
    const store = useUIStore.getState();
    act(() => {
      store.clearSelection();
      store.clearToasts();
      store.closeModal();
      store.closeDrawer();
      store.setSearchQuery("");
      store.closeSearch();
      store.setGlobalLoading(false);
      store.setViewMode("grid");
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("view mode", () => {
    it("should have grid as default view mode", () => {
      const state = useUIStore.getState();
      expect(state.viewMode).toBe("grid");
    });

    it("should set view mode", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.setViewMode("list");
      });

      expect(result.current.viewMode).toBe("list");
    });

    it("should toggle view mode", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.toggleViewMode();
      });
      expect(result.current.viewMode).toBe("list");

      act(() => {
        result.current.toggleViewMode();
      });
      expect(result.current.viewMode).toBe("grid");
    });
  });

  describe("sidebar", () => {
    it("should open sidebar", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.closeSidebar();
      });
      expect(result.current.sidebar.isOpen).toBe(false);

      act(() => {
        result.current.openSidebar();
      });
      expect(result.current.sidebar.isOpen).toBe(true);
    });

    it("should toggle sidebar", () => {
      const { result } = renderHook(() => useUIStore());

      const initialState = result.current.sidebar.isOpen;

      act(() => {
        result.current.toggleSidebar();
      });
      expect(result.current.sidebar.isOpen).toBe(!initialState);
    });

    it("should collapse and expand sidebar", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.collapseSidebar();
      });
      expect(result.current.sidebar.isCollapsed).toBe(true);

      act(() => {
        result.current.expandSidebar();
      });
      expect(result.current.sidebar.isCollapsed).toBe(false);
    });
  });

  describe("drawer", () => {
    it("should open drawer with content type", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.openDrawer("player");
      });

      expect(result.current.drawer.isOpen).toBe(true);
      expect(result.current.drawer.content).toBe("player");
    });

    it("should close drawer and reset content", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.openDrawer("settings");
      });

      act(() => {
        result.current.closeDrawer();
      });

      expect(result.current.drawer.isOpen).toBe(false);
      expect(result.current.drawer.content).toBeNull();
    });
  });

  describe("modal", () => {
    it("should open modal with type and data", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.openModal("bookDetails", { asin: "test-asin" });
      });

      expect(result.current.modal.isOpen).toBe(true);
      expect(result.current.modal.type).toBe("bookDetails");
      expect(result.current.modal.data).toEqual({ asin: "test-asin" });
    });

    it("should close modal and reset state", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.openModal("settings");
      });

      act(() => {
        result.current.closeModal();
      });

      expect(result.current.modal.isOpen).toBe(false);
      expect(result.current.modal.type).toBeNull();
      expect(result.current.modal.data).toBeNull();
    });
  });

  describe("book selection", () => {
    it("should select a book", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.selectBook("asin-1");
      });

      expect(result.current.selectedBooks.has("asin-1")).toBe(true);
    });

    it("should deselect a book", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.selectBook("asin-1");
        result.current.selectBook("asin-2");
      });

      act(() => {
        result.current.deselectBook("asin-1");
      });

      expect(result.current.selectedBooks.has("asin-1")).toBe(false);
      expect(result.current.selectedBooks.has("asin-2")).toBe(true);
    });

    it("should toggle book selection", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.toggleBookSelection("asin-1");
      });
      expect(result.current.selectedBooks.has("asin-1")).toBe(true);

      act(() => {
        result.current.toggleBookSelection("asin-1");
      });
      expect(result.current.selectedBooks.has("asin-1")).toBe(false);
    });

    it("should select all books", () => {
      const { result } = renderHook(() => useUIStore());

      const asins = ["asin-1", "asin-2", "asin-3"];

      act(() => {
        result.current.selectAllBooks(asins);
      });

      expect(result.current.selectedBooks.size).toBe(3);
      expect(result.current.isSelectionMode).toBe(true);
    });

    it("should clear selection", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.selectBook("asin-1");
        result.current.selectBook("asin-2");
      });

      act(() => {
        result.current.clearSelection();
      });

      expect(result.current.selectedBooks.size).toBe(0);
      expect(result.current.isSelectionMode).toBe(false);
    });

    it("should disable selection mode when last book is deselected", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.setSelectionMode(true);
        result.current.selectBook("asin-1");
      });

      act(() => {
        result.current.deselectBook("asin-1");
      });

      expect(result.current.isSelectionMode).toBe(false);
    });
  });

  describe("toasts", () => {
    it("should add a toast", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.addToast({
          type: "success",
          title: "Success",
          message: "Operation completed",
        });
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].type).toBe("success");
      expect(result.current.toasts[0].title).toBe("Success");
    });

    it("should remove a toast by id", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.addToast({ type: "info", title: "Test" });
      });

      const toastId = result.current.toasts[0].id;

      act(() => {
        result.current.removeToast(toastId);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it("should auto-remove toast after duration", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.addToast({
          type: "info",
          title: "Auto-remove",
          duration: 1000,
        });
      });

      expect(result.current.toasts).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(1000);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it("should clear all toasts", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.addToast({ type: "info", title: "Toast 1", duration: 0 });
        result.current.addToast({ type: "error", title: "Toast 2", duration: 0 });
      });

      expect(result.current.toasts).toHaveLength(2);

      act(() => {
        result.current.clearToasts();
      });

      expect(result.current.toasts).toHaveLength(0);
    });
  });

  describe("search", () => {
    it("should set search query", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.setSearchQuery("test query");
      });

      expect(result.current.searchQuery).toBe("test query");
    });

    it("should open and close search", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.openSearch();
      });
      expect(result.current.isSearchOpen).toBe(true);

      act(() => {
        result.current.closeSearch();
      });
      expect(result.current.isSearchOpen).toBe(false);
      expect(result.current.searchQuery).toBe(""); // Should clear query on close
    });

    it("should toggle search", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.toggleSearch();
      });
      expect(result.current.isSearchOpen).toBe(true);

      act(() => {
        result.current.toggleSearch();
      });
      expect(result.current.isSearchOpen).toBe(false);
    });
  });

  describe("global loading", () => {
    it("should set global loading state", () => {
      const { result } = renderHook(() => useUIStore());

      act(() => {
        result.current.setGlobalLoading(true);
      });
      expect(result.current.isGlobalLoading).toBe(true);

      act(() => {
        result.current.setGlobalLoading(false);
      });
      expect(result.current.isGlobalLoading).toBe(false);
    });
  });
});
