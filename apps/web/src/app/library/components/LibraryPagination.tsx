"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { cn } from "@/lib/utils";

export interface LibraryPaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (nextPage: number) => void;
  className?: string;
}

export function LibraryPagination({
  currentPage,
  totalPages,
  onPageChange,
  className,
}: LibraryPaginationProps) {
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
