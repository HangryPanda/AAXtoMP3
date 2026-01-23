import { useSelectedBooks, useUIStore } from "@/store/uiStore";

export function useLibrarySelection() {
  const { selectedBooks, count: selectedCount, isSelectionMode } = useSelectedBooks();
  
  const toggleBookSelection = useUIStore((state) => state.toggleBookSelection);
  const clearSelection = useUIStore((state) => state.clearSelection);
  const setSelectionMode = useUIStore((state) => state.setSelectionMode);
  const selectAllBooks = useUIStore((state) => state.selectAllBooks);

  return {
    selectedBooks,
    selectedCount,
    isSelectionMode,
    toggleBookSelection,
    clearSelection,
    setSelectionMode,
    selectAllBooks,
  };
}
