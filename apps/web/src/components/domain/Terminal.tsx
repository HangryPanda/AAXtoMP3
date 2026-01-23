/**
 * Terminal component for displaying logs with ANSI support
 */
"use client";

import * as React from "react";
import { Search, Copy, Trash2, ChevronUp, ChevronDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

/**
 * Convert ISO timestamp in log line to local time.
 * Matches patterns like: 2024-01-22T02:33:11.123Z or 2024-01-22T02:33:11Z
 */
function convertLogTimestampToLocal(line: string): string {
  const isoPattern = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)/;
  const match = line.match(isoPattern);
  if (match) {
    try {
      const date = new Date(match[1]);
      const localTime = date.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      });
      return line.replace(match[1], localTime);
    } catch {
      return line;
    }
  }
  return line;
}

export interface TerminalProps {
  title?: string;
  height?: number;
  logs?: string[];
  showSearch?: boolean;
  showClearButton?: boolean;
  showCopyButton?: boolean;
  loading?: boolean;
  onSearch?: (query: string) => void;
  onClear?: () => void;
  onCopy?: () => void;
  className?: string;
}

export function Terminal({
  title,
  height = 300,
  logs = [],
  showSearch = false,
  showClearButton = false,
  showCopyButton = false,
  loading = false,
  onSearch,
  onClear,
  onCopy,
  className,
}: TerminalProps) {
  const terminalRef = React.useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = React.useState("");

  // Auto-scroll to bottom when new logs arrive
  React.useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    onSearch?.(value);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(logs.join("\n"));
      onCopy?.();
    } catch (err) {
      console.error("Failed to copy logs:", err);
    }
  };

  const handleFindNext = () => {
    // Find next implementation would go here
    onSearch?.(searchQuery);
  };

  const handleFindPrevious = () => {
    // Find previous implementation would go here
    onSearch?.(searchQuery);
  };

  return (
    <div
      data-testid="terminal-container"
      role="log"
      aria-label={title || "Terminal output"}
      className={cn("flex flex-col rounded-lg border bg-black", className)}
      style={{ height: `${height}px` }}
    >
      {/* Header */}
      {(title || showSearch || showClearButton || showCopyButton) && (
        <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
          {title && (
            <span className="text-sm font-medium text-zinc-400">{title}</span>
          )}

          <div className="flex items-center gap-2">
            {/* Search */}
            {showSearch && (
              <div className="flex items-center gap-1">
                <div className="relative">
                  <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-zinc-500" />
                  <Input
                    type="search"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    className="h-7 w-40 bg-zinc-900 border-zinc-700 pl-7 text-xs text-zinc-300"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-zinc-400 hover:text-zinc-200"
                  onClick={handleFindPrevious}
                  aria-label="Find previous"
                >
                  <ChevronUp className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-zinc-400 hover:text-zinc-200"
                  onClick={handleFindNext}
                  aria-label="Find next"
                >
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </div>
            )}

            {/* Copy */}
            {showCopyButton && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-zinc-400 hover:text-zinc-200"
                onClick={handleCopy}
                aria-label="Copy logs"
              >
                <Copy className="h-3 w-3" />
              </Button>
            )}

            {/* Clear */}
            {showClearButton && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-zinc-400 hover:text-zinc-200"
                onClick={onClear}
                aria-label="Clear terminal"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Terminal Content */}
      <div
        ref={terminalRef}
        className="flex-1 overflow-auto p-3 font-mono text-xs leading-relaxed"
      >
        {loading && (
          <div
            data-testid="terminal-loading"
            className="flex items-center gap-2 text-zinc-500"
          >
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading...
          </div>
        )}

        {!loading && logs.length === 0 && (
          <div className="text-zinc-600">No logs available</div>
        )}

        {!loading &&
          logs.map((line, index) => {
            const displayLine = convertLogTimestampToLocal(line);
            return (
              <div
                key={index}
                className={cn(
                  "whitespace-pre-wrap break-all",
                  line.includes("[ERROR]") || line.includes("error")
                    ? "text-red-400"
                    : line.includes("[WARN]") || line.includes("warn")
                    ? "text-yellow-400"
                    : line.includes("[INFO]")
                    ? "text-blue-400"
                    : line.includes("[SUCCESS]") || line.includes("success")
                    ? "text-green-400"
                    : "text-zinc-300"
                )}
              >
                {displayLine}
              </div>
            );
          })}
      </div>
    </div>
  );
}
