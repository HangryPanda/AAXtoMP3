import { useSyncLibrary, useDeleteBook, useDeleteBooks, useApplyRepair } from "@/hooks/useBooks";
import { useCreateDownloadJob, useCreateConvertJob } from "@/hooks/useJobs";
import { useUIStore } from "@/store/uiStore";

export function useLibraryActions() {
  const addToast = useUIStore((state) => state.addToast);
  const clearSelection = useUIStore((state) => state.clearSelection);

  const { mutate: syncLibrary, isPending: isSyncing } = useSyncLibrary();
  const repairMutation = useApplyRepair();
  const { mutate: downloadBooks } = useCreateDownloadJob();
  const { mutate: convertBook } = useCreateConvertJob();
  const { mutate: deleteBook } = useDeleteBook();
  const { mutate: deleteBooks } = useDeleteBooks();

  const handleBatchDownload = (selectedBooks: string[]) => {
    if (selectedBooks.length > 0) {
      downloadBooks(selectedBooks);
      clearSelection();
      addToast({
        type: "info",
        title: "Download Started",
        message: `Queued ${selectedBooks.length} items for download.`
      });
    }
  };

  const handleBatchConvert = (selectedBooks: string[]) => {
    if (selectedBooks.length > 0) {
      selectedBooks.forEach(asin => convertBook({ asin }));
      clearSelection();
      addToast({
        type: "info",
        title: "Conversion Started",
        message: `Queued ${selectedBooks.length} items for conversion.`
      });
    }
  };

  const handleBatchDelete = (selectedBooks: string[]) => {
    if (selectedBooks.length > 0) {
      if (confirm(`Are you sure you want to delete ${selectedBooks.length} books?`)) {
        deleteBooks(selectedBooks, {
          onSuccess: (data) => {
            addToast({
              type: "success",
              title: "Books Deleted",
              message: `Successfully deleted ${data.deleted} items.`
            });
            clearSelection();
          },
          onError: (err) => {
             addToast({
              type: "error",
              title: "Delete Failed",
              message: err.message
            });
          }
        });
      }
    }
  };

  const handleDeleteBook = (asin: string) => {
      if (confirm("Are you sure you want to delete this book?")) {
        deleteBook(asin, {
           onSuccess: () => {
            addToast({
              type: "success",
              title: "Book Deleted",
              message: "Book has been removed from library."
            });
          },
          onError: (err) => {
             addToast({
              type: "error",
              title: "Delete Failed",
              message: err.message
            });
          }
        });
      }
  };
  
  const handleRepair = () => {
      repairMutation.mutate(undefined, {
          onSuccess: () => {
            addToast({
              type: "info",
              title: "Repair Queued",
              message: "Repair job queued. Check Jobs for progress.",
            });
          },
          onError: (err) => {
            addToast({
              type: "error",
              title: "Repair Failed",
              message: err.message,
            });
          },
        });
  };

  return {
    syncLibrary,
    isSyncing,
    repairMutation,
    handleRepair,
    downloadBooks,
    convertBook,
    handleDeleteBook,
    handleBatchDownload,
    handleBatchConvert,
    handleBatchDelete,
  };
}
