import { useRouter, useSearchParams } from "next/navigation";
import { type SortField, type SortOrder } from "@/components/domain/LibraryToolbar";
import type { LibraryViewType } from "@/components/domain/LibraryViewSwitcher";
import type { BookStatus } from "@/types";

export function useLibraryUrlParams() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const libraryView = (searchParams.get("view") as LibraryViewType) || "library";
  const searchQuery = searchParams.get("search") || "";
  const filterStatus = (searchParams.get("status") as BookStatus) || undefined;
  const contentType =
    ((searchParams.get("content_type") as "audiobook" | "podcast" | null) === "podcast"
      ? "podcast"
      : "audiobook") as "audiobook" | "podcast";
  const seriesValue = searchParams.get("series") || "all";
  const sourceValue = (searchParams.get("source") as "all" | "audible" | "local" | "both") || "all";
  const sortField = (searchParams.get("sort") as SortField) || "purchase_date";
  const sortOrder = (searchParams.get("order") as SortOrder) || "desc";
  const page = parseInt(searchParams.get("page") || "1", 10);

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
      updates.content_type !== undefined ||
      updates.series !== undefined ||
      updates.source !== undefined
    ) {
      params.set("page", "1");
    }
    router.push(`?${params.toString()}`);
  };

  const handleViewChange = (view: LibraryViewType) =>
    updateUrl({ view: view === "library" ? undefined : view });
  const handleSearch = (value: string) => updateUrl({ search: value });
  const handleFilter = (status: BookStatus | undefined) => updateUrl({ status });
  const handleContentType = (value: "audiobook" | "podcast") =>
    updateUrl({ content_type: value === "audiobook" ? undefined : value });
  const handleSeries = (seriesTitle: string | undefined) =>
    updateUrl({ series: seriesTitle });
  const handleSource = (value: "all" | "audible" | "local" | "both") => updateUrl({ source: value });
  const handleSort = (field: SortField, order: SortOrder) => updateUrl({ sort: field, order });
  const handlePageChange = (nextPage: number) => updateUrl({ page: String(nextPage) });
  const handleClearFilters = () =>
    updateUrl({
      search: undefined,
      status: undefined,
      content_type: undefined,
      series: undefined,
      source: undefined,
    });

  const hasActiveFilters =
    !!searchQuery ||
    !!filterStatus ||
    seriesValue !== "all" ||
    sourceValue !== "all" ||
    contentType === "podcast";

  return {
    libraryView,
    searchQuery,
    filterStatus,
    contentType,
    seriesValue,
    sourceValue,
    sortField,
    sortOrder,
    page,
    hasActiveFilters,
    setView: handleViewChange,
    setSearch: handleSearch,
    setFilter: handleFilter,
    setContentType: handleContentType,
    setSeries: handleSeries,
    setSource: handleSource,
    setSort: handleSort,
    setPage: handlePageChange,
    clearFilters: handleClearFilters,
  };
}
