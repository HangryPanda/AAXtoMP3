"use client";

import { Download, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export interface LibraryEmptyStateProps {
  isLoading?: boolean;
  loadingMessage?: string;
  
  isLocal?: boolean; // true for "Local" tab empty state
  
  contentType?: "audiobook" | "podcast";
  searchQuery?: string;
  hasActiveFilters?: boolean;
  
  onClearFilters?: () => void;
  onSync?: () => void;
  isSyncing?: boolean;
  
  className?: string;
}

export function LibraryEmptyState({
  isLoading,
  loadingMessage,
  isLocal,
  contentType = "audiobook",
  searchQuery,
  hasActiveFilters,
  onClearFilters,
  onSync,
  isSyncing,
  className,
}: LibraryEmptyStateProps) {
  if (isLoading) {
    return (
      <div className={cn("flex flex-col items-center justify-center h-64 gap-4", className)}>
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">{loadingMessage || "Loading..."}</p>
      </div>
    );
  }

  if (isLocal) {
    return (
      <div className={cn("flex flex-col items-center justify-center h-80 border-2 border-dashed border-border rounded-xl text-muted-foreground bg-muted/20", className)}>
        <Download className="w-16 h-16 mb-4 opacity-20" />
        <p className="text-xl font-semibold text-foreground">No local items found</p>
        <p className="text-sm text-muted-foreground max-w-xs text-center mt-2 mb-6">
          Import local items to populate this view.
        </p>
      </div>
    );
  }

  // Audible books empty/no-results
  const isNoResults = !!searchQuery || hasActiveFilters;

  return (
    <div className={cn("flex flex-col items-center justify-center h-80 border-2 border-dashed border-border rounded-xl text-muted-foreground bg-muted/20", className)}>
      <Download className="w-16 h-16 mb-4 opacity-20" />
      <p className="text-xl font-semibold text-foreground">
        No {contentType === "podcast" ? "podcasts" : "audiobooks"} found
      </p>
      <p className="text-sm text-muted-foreground max-w-xs text-center mt-2 mb-6">
        {isNoResults
          ? `No results${searchQuery ? ` for "${searchQuery}"` : ""}. Try a different search term or clear your filters.`
          : "Your library is empty. Sync with Audible to import your audiobooks."}
      </p>
      
      {isNoResults && onClearFilters && (
        <Button variant="outline" onClick={onClearFilters}>
          Clear all filters
        </Button>
      )}

      {!isNoResults && onSync && (
        <Button onClick={onSync} disabled={isSyncing} className="gap-2">
          <RefreshCw className={cn("w-4 h-4", isSyncing && "animate-spin")} />
          Sync Library Now
        </Button>
      )}
    </div>
  );
}
