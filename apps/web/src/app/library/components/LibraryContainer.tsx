"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { LibraryToolbar } from "@/components/domain/LibraryToolbar";
import { RepairProgressCard } from "@/components/domain/RepairProgressCard";
import { useUIStore, useViewMode } from "@/store/uiStore";
import { formatDate, formatRelativeDate } from "@/lib/format";

// Hooks
import { useLibraryUrlParams } from "../hooks/useLibraryUrlParams";
import { useLibraryData } from "../hooks/useLibraryData";
import { useLibraryActions } from "../hooks/useLibraryActions";
import { useLibrarySelection } from "../hooks/useLibrarySelection";

// Components
import { LibraryStats } from "./LibraryStats";
import { LibraryPagination } from "./LibraryPagination";
import { LibraryTabs } from "./LibraryTabs";
import { LibrarySelectionBar } from "./LibrarySelectionBar";
import { LibraryEmptyState } from "./LibraryEmptyState";
import { LibraryLocalPreview } from "./LibraryLocalPreview";
import { LibraryBooks } from "./LibraryBooks";
import { LibraryLocalItems } from "./LibraryLocalItems";

export function LibraryContainer() {
  const router = useRouter();
  
  // URL Params
  const {
    searchQuery,
    filterStatus,
    contentType,
    seriesValue,
    sourceValue,
    sortField,
    sortOrder,
    page,
    hasActiveFilters,
    setSearch,
    setFilter,
    setContentType,
    setSeries,
    setSource,
    setSort,
    setPage,
    clearFilters,
  } = useLibraryUrlParams();

  // Data
  const {
    booksData,
    isLoadingBooks,
    localItemsData,
    isLoadingLocalItems,
    localPreviewData,
    seriesOptionsData,
    syncStatusData,
    repairPreview,
    downloadQueueCount,
    convertQueueCount,
    inProgressCount,
    failedCount,
    downloadingTotal,
    convertingTotal,
  } = useLibraryData({
    searchQuery,
    filterStatus,
    contentType,
    seriesValue,
    sourceValue,
    sortField,
    sortOrder,
    page,
  });

  // Actions
  const {
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
  } = useLibraryActions();

  // Selection
  const {
    selectedBooks,
    selectedCount,
    isSelectionMode,
    toggleBookSelection,
    clearSelection,
    setSelectionMode,
    selectAllBooks,
  } = useLibrarySelection();

  // UI Store
  const viewMode = useViewMode();
  const setViewMode = useUIStore((state) => state.setViewMode);
  const openProgressPopover = useUIStore((state) => state.openProgressPopover);
  const isRepairProgressCardVisible = useUIStore((s) => s.isRepairProgressCardVisible);

  // Derived
  const sortedBooks = useMemo(() => {
    return booksData?.items ?? [];
  }, [booksData]);

  const handleSelectAll = () => {
    if (booksData) {
      selectAllBooks(booksData.items.map(b => b.asin));
    }
  };

  const handleBookPlay = (asin: string) => router.push(`/player?asin=${asin}`);
  const handleLocalPlay = (id: string) => router.push(`/player?local_id=${id}`);

  return (
    <div className="flex flex-col h-full">
      {/* Stats Bar */}
      <LibraryStats
        totalBooks={repairPreview?.remote_total ?? syncStatusData?.total_books ?? booksData?.total ?? 0}
        downloadedCount={repairPreview?.downloaded_db_total ?? repairPreview?.downloaded_on_disk_remote_total ?? repairPreview?.downloaded_total ?? 0}
        convertedCount={repairPreview?.converted_db_total ?? repairPreview?.converted_m4b_titles_on_disk_total ?? repairPreview?.converted_total ?? 0}
        downloadQueueCount={downloadQueueCount}
        convertQueueCount={convertQueueCount}
        inProgressCount={inProgressCount}
        failedCount={failedCount}
        downloadingTotal={downloadingTotal}
        convertingTotal={convertingTotal}
        onOpenProgressPopover={openProgressPopover}
        repairPreview={repairPreview}
      />

      {sourceValue !== "local" && isRepairProgressCardVisible && <RepairProgressCard className="mb-6" />}

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
          onSearchChange={setSearch}
          onFilterChange={setFilter}
          onSourceChange={setSource}
          onSeriesChange={setSeries}
          onSortChange={setSort}
          onViewChange={setViewMode}
        />

        {/* Audiobooks / Podcasts Tabs */}
        {sourceValue !== "local" && (
          <LibraryTabs
            contentType={contentType}
            onContentTypeChange={setContentType}
          />
        )}

        {/* Selection Bar (Audible lists only) */}
        {sourceValue !== "local" && (
          <LibrarySelectionBar
            isSelectionMode={isSelectionMode}
            selectedCount={selectedCount}
            onToggleSelectionMode={() => setSelectionMode(!isSelectionMode)}
            onSelectAllPage={handleSelectAll}
            onClearSelection={clearSelection}
            onBatchDelete={() => handleBatchDelete(selectedBooks)}
            onBatchDownload={() => handleBatchDownload(selectedBooks)}
            onBatchConvert={() => handleBatchConvert(selectedBooks)}
            onRepair={handleRepair}
            isRepairPending={repairMutation.isPending}
            onSync={() => syncLibrary()}
            isSyncing={isSyncing}
            lastSyncText={
              syncStatusData?.last_sync_completed_at
                ? `Last sync: ${formatRelativeDate(syncStatusData.last_sync_completed_at)} (${formatDate(syncStatusData.last_sync_completed_at, "MMM d, yyyy h:mm a")})`
                : "Last sync: -"
            }
          />
        )}

        {sourceValue !== "local" && (
          <LibraryPagination
            className="px-1"
            currentPage={booksData?.page ?? page}
            totalPages={booksData?.total_pages ?? 1}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* Content */}
      <main className="flex-1 min-h-0">
        {/* Local-only preview section */}
        {sourceValue === "all" && (
          <LibraryLocalPreview
            items={localPreviewData?.items ?? []}
            total={localPreviewData?.total ?? 0}
            viewMode={viewMode}
            onViewLocal={() => setSource("local")}
            onPlay={handleLocalPlay}
          />
        )}

        {sourceValue === "local" ? (
            (isLoadingLocalItems || (localItemsData?.items.length === 0)) ? (
                <LibraryEmptyState
                    isLoading={isLoadingLocalItems}
                    loadingMessage="Loading local library..."
                    isLocal={!isLoadingLocalItems}
                />
            ) : (
                <>
                  <LibraryLocalItems
                    items={localItemsData?.items ?? []}
                    viewMode={viewMode}
                  />
                  <LibraryPagination
                    currentPage={localItemsData?.page ?? page}
                    totalPages={localItemsData?.total_pages ?? 1}
                    onPageChange={setPage}
                  />
                </>
            )
        ) : (
            (isLoadingBooks || sortedBooks.length === 0) ? (
                <LibraryEmptyState
                    isLoading={isLoadingBooks}
                    loadingMessage="Loading your library..."
                    contentType={contentType}
                    searchQuery={searchQuery}
                    hasActiveFilters={hasActiveFilters}
                    onClearFilters={clearFilters}
                    onSync={() => syncLibrary()}
                    isSyncing={isSyncing}
                />
            ) : (
                <LibraryBooks
                    books={sortedBooks}
                    viewMode={viewMode}
                    isSelectionMode={isSelectionMode}
                    selectedBooks={selectedBooks}
                    onToggleSelection={toggleBookSelection}
                    onPlay={handleBookPlay}
                    onDownload={(asin) => downloadBooks(asin)}
                    onConvert={(params) => convertBook(params)}
                    onDelete={handleDeleteBook}
                />
            )
        )}
        
        {sourceValue !== "local" && (
          <div className="mt-6 pb-10">
            <LibraryPagination
              currentPage={booksData?.page ?? page}
              totalPages={booksData?.total_pages ?? 1}
              onPageChange={setPage}
            />
          </div>
        )}
      </main>
    </div>
  );
}
