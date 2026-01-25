/**
 * LibraryToolbar component with search, filter, sort, and view toggle
 */
import * as React from "react";
import { Search, Grid3X3, List, Filter, SortAsc, Layers, Cloud, HardDrive } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { STATUS_LABELS, type BookStatus, type SeriesOption } from "@/types";

export type ViewMode = "grid" | "list";
export type SortField = "title" | "purchase_date" | "runtime_length_min" | "created_at";
export type SortOrder = "asc" | "desc";

export interface LibraryToolbarProps {
  searchValue?: string;
  filterValue?: BookStatus | "all";
  sourceValue?: "all" | "audible" | "local" | "both";
  seriesValue?: string;
  seriesOptions?: SeriesOption[];
  noSeriesCount?: number;
  sortField?: SortField;
  sortOrder?: SortOrder;
  viewMode?: ViewMode;
  onSearchChange?: (value: string) => void;
  onFilterChange?: (status: BookStatus | undefined) => void;
  onSourceChange?: (value: "all" | "audible" | "local" | "both") => void;
  onSeriesChange?: (seriesTitle: string | undefined) => void;
  onSortChange?: (field: SortField, order: SortOrder) => void;
  onViewChange?: (mode: ViewMode) => void;
  className?: string;
}

// Status options for filter dropdown
const FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All Status" },
  ...Object.entries(STATUS_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
];

// Sort options
const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: "title", label: "Title" },
  { value: "purchase_date", label: "Purchase Date" },
  { value: "runtime_length_min", label: "Duration" },
  { value: "created_at", label: "Date Added" },
];

export function LibraryToolbar({
  searchValue = "",
  filterValue = "all",
  sourceValue = "all",
  seriesValue = "all",
  seriesOptions = [],
  noSeriesCount,
  sortField = "purchase_date",
  sortOrder = "desc",
  viewMode = "grid",
  onSearchChange,
  onFilterChange,
  onSourceChange,
  onSeriesChange,
  onSortChange,
  onViewChange,
  className,
}: LibraryToolbarProps) {
  const [localSearch, setLocalSearch] = React.useState(searchValue);
  const [isSearchExpanded, setIsSearchExpanded] = React.useState(Boolean(searchValue));
  const debounceTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const searchInputRef = React.useRef<HTMLInputElement | null>(null);

  // Debounced search
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setLocalSearch(value);

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    debounceTimer.current = setTimeout(() => {
      onSearchChange?.(value);
    }, 300);
  };

  // Cleanup debounce on unmount
  React.useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  // Sync local search with external value
  React.useEffect(() => {
    setLocalSearch(searchValue);
    setIsSearchExpanded(Boolean(searchValue));
  }, [searchValue]);

  const expandSearch = () => {
    setIsSearchExpanded(true);
    // Let the input mount/resize before focusing
    requestAnimationFrame(() => searchInputRef.current?.focus());
  };

  const collapseSearch = () => {
    setIsSearchExpanded(false);
  };

  const handleFilterChange = (value: string) => {
    if (value === "all") {
      onFilterChange?.(undefined);
    } else {
      onFilterChange?.(value as BookStatus);
    }
  };

  const handleSourceChange = (value: string) => {
    if (value === "all" || value === "audible" || value === "local" || value === "both") {
      onSourceChange?.(value);
    }
  };

  const handleSeriesChange = (value: string) => {
    if (value === "all") {
      onSeriesChange?.(undefined);
      return;
    }
    onSeriesChange?.(value);
  };

  const handleSortChange = (value: string) => {
    onSortChange?.(value as SortField, sortOrder);
  };

  const toggleSortOrder = () => {
    onSortChange?.(sortField, sortOrder === "asc" ? "desc" : "asc");
  };

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-4 py-4",
        className
      )}
    >
      {/* Filter */}
      <Select
        value={filterValue}
        onValueChange={handleFilterChange}
      >
        <SelectTrigger
          className="w-[190px]"
          aria-label="Filter by status"
        >
          <Filter className="mr-2 h-4 w-4" />
          <SelectValue placeholder="Filter" />
        </SelectTrigger>
        <SelectContent>
          {FILTER_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Source */}
      <Select
        value={sourceValue}
        onValueChange={handleSourceChange}
      >
        <SelectTrigger
          className="w-[170px]"
          aria-label="Filter by source"
        >
          <Cloud className="mr-2 h-4 w-4" />
          <SelectValue placeholder="Source" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All</SelectItem>
          <SelectItem value="audible">
            <span className="inline-flex items-center gap-2">
              <Cloud className="h-4 w-4" /> Audible
            </span>
          </SelectItem>
          <SelectItem value="local">
            <span className="inline-flex items-center gap-2">
              <HardDrive className="h-4 w-4" /> Local
            </span>
          </SelectItem>
          <SelectItem value="both">Audible + Local</SelectItem>
        </SelectContent>
      </Select>

      {/* Series */}
      <Select
        value={seriesValue}
        onValueChange={handleSeriesChange}
      >
        <SelectTrigger
          className="w-[220px]"
          aria-label="Filter by series"
        >
          <Layers className="mr-2 h-4 w-4" />
          <SelectValue placeholder="Series" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Series</SelectItem>
          <SelectItem value="__none__">
            No Series{typeof noSeriesCount === "number" ? ` (${noSeriesCount})` : ""}
          </SelectItem>
          {seriesOptions.map((s) => (
            <SelectItem key={s.title} value={s.title}>
              {s.title} ({s.count})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Sort */}
      <div className="flex items-center gap-1">
        <Select
          value={sortField}
          onValueChange={handleSortChange}
        >
          <SelectTrigger
            className="w-[150px]"
            aria-label="Sort by"
          >
            <SortAsc className="mr-2 h-4 w-4" />
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSortOrder}
          aria-label={`Sort ${sortOrder === "asc" ? "descending" : "ascending"}`}
        >
          <SortAsc
            className={cn(
              "h-4 w-4 transition-transform",
              sortOrder === "desc" && "rotate-180"
            )}
          />
        </Button>
      </div>

      {/* View Toggle */}
      <div className="flex items-center rounded-md border">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onViewChange?.("grid")}
          aria-label="Grid view"
          aria-pressed={viewMode === "grid"}
          className={cn(
            "rounded-r-none",
            viewMode === "grid" && "bg-accent"
          )}
        >
          <Grid3X3 className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onViewChange?.("list")}
          aria-label="List view"
          aria-pressed={viewMode === "list"}
          className={cn(
            "rounded-l-none",
            viewMode === "list" && "bg-accent"
          )}
        >
          <List className="h-4 w-4" />
        </Button>
      </div>

      {/* Search (right-justified; expands left) */}
      <div className="ml-auto flex items-center justify-end">
        <div
          className={cn(
            "relative overflow-hidden transition-all duration-200 ease-out",
            isSearchExpanded ? "w-[280px] opacity-100" : "w-0 opacity-0 pointer-events-none"
          )}
          aria-hidden={!isSearchExpanded}
        >
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            ref={searchInputRef}
            type="search"
            role="searchbox"
            placeholder="Search books..."
            value={localSearch}
            onChange={handleSearchChange}
            tabIndex={isSearchExpanded ? 0 : -1}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                collapseSearch();
                (e.currentTarget as HTMLInputElement).blur();
              }
            }}
            onBlur={() => {
              if (!localSearch.trim()) collapseSearch();
            }}
            className="pl-9 pr-3"
          />
        </div>

        <Button
          variant="outline"
          size="icon"
          className={cn("rounded-full", isSearchExpanded && "ml-2")}
          aria-label={isSearchExpanded ? "Focus search" : "Open search"}
          aria-expanded={isSearchExpanded}
          onClick={() => {
            if (!isSearchExpanded) expandSearch();
            else searchInputRef.current?.focus();
          }}
        >
          <Search className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
