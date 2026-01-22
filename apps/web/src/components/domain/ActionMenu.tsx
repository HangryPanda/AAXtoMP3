/**
 * ActionMenu component for book actions
 */
import * as React from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  MoreVertical,
  Download,
  FileAudio,
  Play,
  Info,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { canDownload, canConvert, canPlay, type Book } from "@/types";

export interface ActionMenuProps {
  book: Book;
  onDownload?: (book: Book) => void;
  onConvert?: (book: Book) => void;
  onPlay?: (book: Book) => void;
  onViewDetails?: (book: Book) => void;
  onDelete?: (book: Book) => void;
  className?: string;
}

export function ActionMenu({
  book,
  onDownload,
  onConvert,
  onPlay,
  onViewDetails,
  onDelete,
  className,
}: ActionMenuProps) {
  const showDownload = canDownload(book);
  const showConvert = canConvert(book);
  const showPlay = canPlay(book);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn("h-8 w-8", className)}
          aria-label="Actions"
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="z-50 min-w-[160px] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-80 data-[side=bottom]:slide-in-from-top-2"
          align="end"
          sideOffset={4}
        >
          {showDownload && (
            <DropdownMenu.Item
              className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
              onSelect={() => onDownload?.(book)}
            >
              <Download className="mr-2 h-4 w-4" />
              Download
            </DropdownMenu.Item>
          )}

          {showConvert && (
            <DropdownMenu.Item
              className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
              onSelect={() => onConvert?.(book)}
            >
              <FileAudio className="mr-2 h-4 w-4" />
              Convert
            </DropdownMenu.Item>
          )}

          {showPlay && (
            <DropdownMenu.Item
              className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
              onSelect={() => onPlay?.(book)}
            >
              <Play className="mr-2 h-4 w-4" />
              Play
            </DropdownMenu.Item>
          )}

          <DropdownMenu.Separator className="mx-1 my-1 h-px bg-muted" />

          <DropdownMenu.Item
            className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
            onSelect={() => onViewDetails?.(book)}
          >
            <Info className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenu.Item>

          {onDelete && (
            <>
              <DropdownMenu.Separator className="mx-1 my-1 h-px bg-muted" />
              <DropdownMenu.Item
                className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm text-destructive outline-none transition-colors hover:bg-destructive hover:text-destructive-foreground focus:bg-destructive focus:text-destructive-foreground"
                onSelect={() => onDelete(book)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenu.Item>
            </>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
