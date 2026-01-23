import { useMemo } from "react";
import { useBooks, useLocalItems, useSeriesOptions, useLibrarySyncStatus, useRepairPreview, useBooksByStatus } from "@/hooks/useBooks";
import { useActiveJobs, useJobs } from "@/hooks/useJobs";
import type { BookStatus } from "@/types";
import type { SortField, SortOrder } from "@/components/domain/LibraryToolbar";

interface UseLibraryDataParams {
  searchQuery: string;
  filterStatus?: BookStatus;
  contentType: "audiobook" | "podcast";
  seriesValue: string;
  sourceValue: "all" | "audible" | "local" | "both";
  sortField: SortField;
  sortOrder: SortOrder;
  page: number;
}

export function useLibraryData({
  searchQuery,
  filterStatus,
  contentType,
  seriesValue,
  sourceValue,
  sortField,
  sortOrder,
  page,
}: UseLibraryDataParams) {
  
  // Data Fetching
  const { 
    data: booksData, 
    isLoading: isLoadingBooks,
  } = useBooks({ 
    search: searchQuery,
    status: filterStatus,
    content_type: contentType,
    series_title: seriesValue === "all" ? undefined : seriesValue,
    has_local: sourceValue === "both" ? true : undefined,
    sort_by: sortField,
    sort_order: sortOrder,
    page: page,
    page_size: 50 
  }, { enabled: sourceValue !== "local" });

  const { data: localItemsData, isLoading: isLoadingLocalItems } = useLocalItems(
    { page, page_size: 50, search: searchQuery || undefined },
    { enabled: sourceValue !== "audible" && sourceValue !== "both" }
  );

  // In "all" mode, show a small "local-only" preview section (page 1, independent of Audible pagination)
  const { data: localPreviewData } = useLocalItems(
    { page: 1, page_size: 50, search: searchQuery || undefined },
    { enabled: sourceValue === "all" }
  );

  const { data: seriesOptionsData } = useSeriesOptions();
  const { data: syncStatusData } = useLibrarySyncStatus();
  const { data: repairPreview } = useRepairPreview({ enabled: sourceValue !== "local" });

  // Stats
  const { data: activeJobs } = useActiveJobs();
  const { data: failedJobs } = useJobs("FAILED");
  const { data: convertingBooks } = useBooksByStatus("CONVERTING", { page_size: 1 });
  const { data: downloadingBooks } = useBooksByStatus("DOWNLOADING", { page_size: 1 });

  const downloadQueueCount = useMemo(
    () => activeJobs?.items.filter((j) => j.task_type === "DOWNLOAD").length ?? 0,
    [activeJobs]
  );
  const convertQueueCount = useMemo(
    () => activeJobs?.items.filter((j) => j.task_type === "CONVERT").length ?? 0,
    [activeJobs]
  );

  const inProgressCount = useMemo(() => {
    const totals = [downloadingBooks?.total ?? 0, convertingBooks?.total ?? 0];
    return totals.reduce((sum, n) => sum + n, 0);
  }, [downloadingBooks, convertingBooks]);
  
  const failedCount = failedJobs?.total ?? 0;

  return {
    booksData,
    isLoadingBooks,
    localItemsData,
    isLoadingLocalItems,
    localPreviewData,
    seriesOptionsData,
    syncStatusData,
    repairPreview,
    
    // Stats
    downloadQueueCount,
    convertQueueCount,
    inProgressCount,
    failedCount,
    downloadingTotal: downloadingBooks?.total ?? 0,
    convertingTotal: convertingBooks?.total ?? 0,
  };
}
