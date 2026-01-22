"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Download,
  Loader2,
  RefreshCw,
  Trash2,
  FileAudio,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Wrench,
  AlertCircle,
} from "lucide-react";
import { useBooks, useSyncLibrary, useBooksByStatus, useDeleteBook, useDeleteBooks, useSeriesOptions, useLibrarySyncStatus, useLocalItems, useRepairPreview, useApplyRepair } from "@/hooks/useBooks";
import { useActiveJobs, useJobs, useCreateDownloadJob, useCreateConvertJob } from "@/hooks/useJobs";
import { BookCard } from "@/components/domain/BookCard";
import { BookRow } from "@/components/domain/BookRow";
import { LocalItemCard } from "@/components/domain/LocalItemCard";
import { LocalItemRow } from "@/components/domain/LocalItemRow";
import { RepairProgressCard } from "@/components/domain/RepairProgressCard";
import { ProgressPopover } from "@/components/domain/ProgressPopover";
import { LibraryToolbar, type SortField, type SortOrder } from "@/components/domain/LibraryToolbar";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useUIStore, useViewMode, useSelectedBooks } from "@/store/uiStore";
import type { BookStatus } from "@/types";
import { cn } from "@/lib/utils";
import { formatDate, formatRelativeDate } from "@/lib/format";

function PaginationControls({
  currentPage,
  totalPages,
  onPageChange,
  className,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (nextPage: number) => void;
  className?: string;
}) {
  if (totalPages <= 1) return null;

  const canPrev = currentPage > 1;
  const canNext = currentPage < totalPages;

  return (
    <div className={cn("flex items-center justify-center gap-2", className)}>
      <Button
        size="icon"
        variant="outline"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={!canPrev}
        aria-label="Previous page"
        className="h-8 w-8"
      >
        <ChevronLeft className="w-4 h-4" />
      </Button>

      <div className="relative group">
        <div className="text-sm text-muted-foreground tabular-nums px-2 py-1 rounded-md group-hover:opacity-0 transition-opacity absolute inset-0 flex items-center justify-center pointer-events-none">
          Page <span className="font-medium text-foreground mx-1">{currentPage}</span> of{" "}
          <span className="font-medium text-foreground mx-1">{totalPages}</span>
        </div>
        
        <div className="opacity-0 group-hover:opacity-100 transition-opacity min-w-[140px]">
          <Select
            value={String(currentPage)}
            onValueChange={(value) => onPageChange(parseInt(value, 10))}
          >
            <SelectTrigger className="h-8 w-full border-muted-foreground/20 bg-background">
              <SelectValue placeholder={`Page ${currentPage}`} />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <SelectItem key={page} value={String(page)}>
                  Page {page}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        
        {/* Placeholder to maintain width when not hovering */}
        <div className="invisible h-8 min-w-[140px]" aria-hidden="true">
           Page {currentPage} of {totalPages}
        </div>
      </div>

      <Button
        size="icon"
        variant="outline"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={!canNext}
        aria-label="Next page"
        className="h-8 w-8"
      >
        <ChevronRight className="w-4 h-4" />
      </Button>
    </div>
  );
}

function LibraryContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const addToast = useUIStore((state) => state.addToast);
  
  // URL States
  const searchQuery = searchParams.get("search") || "";
  const filterStatus = (searchParams.get("status") as BookStatus) || undefined;
  const seriesValue = searchParams.get("series") || "all";
  const sourceValue = (searchParams.get("source") as "all" | "audible" | "local" | "both") || "all";
  const sortField = (searchParams.get("sort") as SortField) || "purchase_date";
  const sortOrder = (searchParams.get("order") as SortOrder) || "desc";
  const page = parseInt(searchParams.get("page") || "1", 10);

  // UI Store
  const viewMode = useViewMode();
  const setViewMode = useUIStore((state) => state.setViewMode);
  const { selectedBooks, count: selectedCount, isSelectionMode } = useSelectedBooks();
  const { 
    toggleBookSelection, 
    clearSelection, 
    setSelectionMode,
    selectAllBooks,
    openProgressPopover
  } = useUIStore();

  // Data Fetching
  const { 
    data: booksData, 
    isLoading: isLoadingBooks,
  } = useBooks({ 
    search: searchQuery,
    status: filterStatus,
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

  const { mutate: syncLibrary, isPending: isSyncing } = useSyncLibrary();
  const repairMutation = useApplyRepair();
  const { mutate: downloadBooks } = useCreateDownloadJob();
  const { mutate: convertBook } = useCreateConvertJob();
  const { mutate: deleteBook } = useDeleteBook();
  const { mutate: deleteBooks } = useDeleteBooks();

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

  // URL Sync Handlers
  const updateUrl = (updates: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([key, value]) => {
      if (value) params.set(key, value);
      else params.delete(key);
    });
    // Reset page on filter/search change
    if (
      updates.search !== undefined ||
      updates.status !== undefined ||
      updates.series !== undefined ||
      updates.source !== undefined
    ) {
      params.set("page", "1");
    }
    router.push(`?${params.toString()}`);
  };

  const handleSearch = (value: string) => updateUrl({ search: value });
  const handleFilter = (status: BookStatus | undefined) => updateUrl({ status });
  const handleSeries = (seriesTitle: string | undefined) =>
    updateUrl({ series: seriesTitle });
  const handleSource = (value: "all" | "audible" | "local" | "both") => updateUrl({ source: value });
  const handleSort = (field: SortField, order: SortOrder) => updateUrl({ sort: field, order });
  const handlePageChange = (nextPage: number) => updateUrl({ page: String(nextPage) });

  // Actions
  const handleBatchDownload = () => {
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

  const handleBatchConvert = () => {
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

  const handleBatchDelete = () => {
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

  const handleSelectAll = () => {
    if (booksData) {
      selectAllBooks(booksData.items.map(b => b.asin));
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Stats Bar */}
      <div className="flex gap-4 mb-6 overflow-x-auto pb-2">
        <div className="bg-card border border-border rounded-lg px-4 py-3 min-w-[140px] shadow-sm">
          <div className="text-2xl font-bold">{repairPreview?.remote_total ?? syncStatusData?.total_books ?? booksData?.total ?? 0}</div>
          <div className="text-sm text-muted-foreground">Total Books</div>
        </div>
        <div className="bg-card border border-border rounded-lg px-4 py-3 min-w-[160px] shadow-sm">
          <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-500">
            {repairPreview?.downloaded_total ?? 0}
          </div>
          <div className="text-sm text-muted-foreground">Downloaded</div>
          <div className="text-xs text-muted-foreground/80">
            Download queue: {downloadQueueCount}
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg px-4 py-3 min-w-[140px] shadow-sm">
          <div className="text-2xl font-bold text-green-600 dark:text-green-500">
            {repairPreview?.converted_total ?? 0}
          </div>
          <div className="text-sm text-muted-foreground">Converted</div>
          <div className="text-xs text-muted-foreground/80">
            Convert queue: {convertQueueCount}
          </div>
          {repairPreview && (
            <div className="text-xs text-muted-foreground/80">
              Of downloaded: {repairPreview.converted_of_downloaded}
            </div>
          )}
        </div>
        <div 
          className="bg-card border border-border rounded-lg px-4 py-3 min-w-[160px] shadow-sm cursor-pointer hover:bg-muted/50 transition-colors relative"
          onClick={openProgressPopover}
        >
          {inProgressCount > 0 && (
            <span className="absolute top-3 right-3 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500"></span>
            </span>
          )}
          {failedCount > 0 && (
             <span className="absolute top-3 right-3 flex h-3 w-3 items-center justify-center">
               <AlertCircle className="h-3 w-3 text-destructive animate-pulse" />
             </span>
          )}
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-500 flex items-center gap-2">
            {inProgressCount}
            {failedCount > 0 && <span className="text-sm font-normal text-destructive ml-1">({failedCount} failed)</span>}
          </div>
          <div className="text-sm text-muted-foreground">In Progress</div>
          <div className="text-xs text-muted-foreground/80">
            Downloading: {downloadingBooks?.total ?? 0}
          </div>
          <div className="text-xs text-muted-foreground/80">
            Converting: {convertingBooks?.total ?? 0}
          </div>
        </div>
      </div>

      {sourceValue !== "local" && <RepairProgressCard className="mb-6" />}

      {/* Toolbar */}
      <div className="flex flex-col gap-4 mb-6">
        <LibraryToolbar
          searchValue={searchQuery}
          filterValue={filterStatus || "all"}
          sourceValue={sourceValue}
          seriesValue={seriesValue}
          seriesOptions={seriesOptionsData?.items ?? []}
          noSeriesCount={seriesOptionsData?.no_series_count}
          sortField={sortField}
          sortOrder={sortOrder}
          viewMode={viewMode}
          onSearchChange={handleSearch}
          onFilterChange={handleFilter}
          onSourceChange={handleSource}
          onSeriesChange={handleSeries}
          onSortChange={handleSort}
          onViewChange={setViewMode}
        />

        {/* Selection Bar (Audible lists only) */}
        {sourceValue !== "local" && (
          <div className="flex items-center justify-between h-10 px-1">
            <div className="flex items-center gap-4">
              <Button 
                variant={isSelectionMode ? "default" : "outline"}
                size="sm" 
                onClick={() => setSelectionMode(!isSelectionMode)}
                className={
                  isSelectionMode
                    ? "gap-2 bg-primary text-primary-foreground"
                    : "gap-2 border-primary/60 text-primary hover:bg-primary/10"
                }
              >
                <CheckSquare className="w-4 h-4" />
                {isSelectionMode ? "Exit Selection" : "Select Items"}
              </Button>

              {isSelectionMode && (
                <>
                  <span className="text-sm font-medium">{selectedCount} selected</span>
                  <Button variant="ghost" size="sm" onClick={handleSelectAll}>Select All Page</Button>
                  <Button variant="ghost" size="sm" onClick={clearSelection}>Clear</Button>
                </>
              )}
            </div>

            <div className="flex items-center gap-2">
              {isSelectionMode && selectedCount > 0 && (
                <>
                  <Button size="sm" variant="destructive" className="gap-2" onClick={handleBatchDelete}>
                    <Trash2 className="w-4 h-4" />
                    Delete Selected
                  </Button>
                  <Button size="sm" className="gap-2" onClick={handleBatchDownload}>
                    <Download className="w-4 h-4" />
                    Download Selected
                  </Button>
                  <Button size="sm" className="gap-2" onClick={handleBatchConvert}>
                    <FileAudio className="w-4 h-4" />
                    Convert Selected
                  </Button>
                </>
              )}
              
              {!isSelectionMode && (
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
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
                        })
                      }
                      disabled={repairMutation.isPending}
                      className="gap-2"
                    >
                      <Wrench className={cn("w-4 h-4", repairMutation.isPending && "animate-spin")} />
                      Repair
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => syncLibrary()}
                      disabled={isSyncing}
                      className="gap-2"
                    >
                      <RefreshCw className={cn("w-4 h-4", isSyncing && "animate-spin")} />
                      Sync Audible
                    </Button>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {syncStatusData?.last_sync_completed_at
                      ? `Last sync: ${formatRelativeDate(syncStatusData.last_sync_completed_at)} (${formatDate(syncStatusData.last_sync_completed_at, "MMM d, yyyy h:mm a")})`
                      : "Last sync: -"}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {sourceValue !== "local" && (
          <PaginationControls
            className="px-1"
            currentPage={booksData?.page ?? page}
            totalPages={booksData?.total_pages ?? 1}
            onPageChange={handlePageChange}
          />
        )}
      </div>

      {/* Content */}
      <main className="flex-1 min-h-0">
        {/* Local-only preview section */}
        {sourceValue === "all" && (localPreviewData?.items?.length ?? 0) > 0 && (
          <section className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-muted-foreground">
                Local-only ({localPreviewData?.total ?? 0})
              </h2>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleSource("local")}
              >
                View Local
              </Button>
            </div>
            <div
              className={cn(
                viewMode === "grid"
                  ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6"
                  : "space-y-1"
              )}
            >
              {localPreviewData?.items.map((it) =>
                viewMode === "grid" ? (
                  <LocalItemCard
                    key={it.id}
                    item={it}
                    onPlay={() => router.push(`/player?local_id=${it.id}`)}
                  />
                ) : (
                  <LocalItemRow
                    key={it.id}
                    item={it}
                    onRowClick={() => router.push(`/player?local_id=${it.id}`)}
                    onPlay={() => router.push(`/player?local_id=${it.id}`)}
                  />
                )
              )}
            </div>
          </section>
        )}

        {sourceValue === "local" ? (
          isLoadingLocalItems ? (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">Loading local library...</p>
            </div>
          ) : localItemsData?.items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-80 border-2 border-dashed border-border rounded-xl text-muted-foreground bg-muted/20">
              <Download className="w-16 h-16 mb-4 opacity-20" />
              <p className="text-xl font-semibold text-foreground">No local items found</p>
              <p className="text-sm text-muted-foreground max-w-xs text-center mt-2 mb-6">
                Import local items to populate this view.
              </p>
            </div>
          ) : (
            <>
              <div
                className={cn(
                  "pb-10",
                  viewMode === "grid"
                    ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6"
                    : "space-y-1"
                )}
              >
                {localItemsData?.items.map((it) =>
                  viewMode === "grid" ? (
                    <LocalItemCard
                      key={it.id}
                      item={it}
                      onPlay={() => router.push(`/player?local_id=${it.id}`)}
                    />
                  ) : (
                    <LocalItemRow
                      key={it.id}
                      item={it}
                      onRowClick={() => router.push(`/player?local_id=${it.id}`)}
                      onPlay={() => router.push(`/player?local_id=${it.id}`)}
                    />
                  )
                )}
              </div>
              <PaginationControls
                currentPage={localItemsData?.page ?? page}
                totalPages={localItemsData?.total_pages ?? 1}
                onPageChange={handlePageChange}
              />
            </>
          )
        ) : isLoadingBooks ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading your library...</p>
          </div>
        ) : booksData?.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-80 border-2 border-dashed border-border rounded-xl text-muted-foreground bg-muted/20">
            <Download className="w-16 h-16 mb-4 opacity-20" />
            <p className="text-xl font-semibold text-foreground">No books found</p>
            <p className="text-sm text-muted-foreground max-w-xs text-center mt-2 mb-6">
              {searchQuery 
                ? `No results for "${searchQuery}". Try a different search term or clear your filters.` 
                : "Your library is empty. Sync with Audible to import your audiobooks."}
            </p>
            {!searchQuery ? (
              <Button onClick={() => syncLibrary()} disabled={isSyncing} className="gap-2">
                <RefreshCw className={cn("w-4 h-4", isSyncing && "animate-spin")} />
                Sync Library Now
              </Button>
            ) : (
              <Button variant="outline" onClick={() => updateUrl({ search: undefined, status: undefined })}>
                Clear all filters
              </Button>
            )}
          </div>
        ) : (
          <div className={cn(
            "pb-10",
            viewMode === "grid" 
              ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6"
              : "space-y-1"
          )}>
            {booksData?.items.map((book) => (
              viewMode === "grid" ? (
                <BookCard
                  key={book.asin}
                  book={book}
                  selectable={isSelectionMode}
                  selected={selectedBooks.includes(book.asin)}
                  onSelect={() => toggleBookSelection(book.asin)}
                  onPlay={() => router.push(`/player?asin=${book.asin}`)}
                  onDownload={() => downloadBooks(book.asin)}
                  onConvert={() => convertBook({ asin: book.asin })}
                  onAction={(action) => {
                    if (action === "delete") handleDeleteBook(book.asin);
                  }}
                />
              ) : (
                <BookRow
                  key={book.asin}
                  book={book}
                  selectable={isSelectionMode}
                  selected={selectedBooks.includes(book.asin)}
                  onSelect={() => toggleBookSelection(book.asin)}
                  onPlay={() => router.push(`/player?asin=${book.asin}`)}
                  onDownload={() => downloadBooks(book.asin)}
                  onConvert={() => convertBook({ asin: book.asin })}
                  onDelete={() => handleDeleteBook(book.asin)}
                  onRowClick={(b) => {
                    if (isSelectionMode) {
                      toggleBookSelection(b.asin);
                    } else {
                      router.push(`/player?asin=${b.asin}`);
                    }
                  }}
                />
              )
            ))}
          </div>
        )}
        {sourceValue !== "local" && (
          <div className="mt-6 pb-10">
            <PaginationControls
              currentPage={booksData?.page ?? page}
              totalPages={booksData?.total_pages ?? 1}
              onPageChange={handlePageChange}
            />
          </div>
        )}
      </main>
      <ProgressPopover />
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    }>
      <LibraryContent />
    </Suspense>
  );
}
