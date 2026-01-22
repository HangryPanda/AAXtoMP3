/**
 * Header component with title, search, and actions
 */
import * as React from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/Input";

export interface HeaderProps {
  title?: string;
  subtitle?: string;
  searchValue?: string;
  onSearch?: (value: string) => void;
  actions?: React.ReactNode;
  className?: string;
}

export function Header({
  title = "Library",
  subtitle,
  searchValue,
  onSearch,
  actions,
  className,
}: HeaderProps) {
  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onSearch?.(event.target.value);
  };

  return (
    <header
      role="banner"
      className={cn(
        "flex items-center justify-between px-6 py-4 border-b border-border bg-background",
        className
      )}
    >
      {/* Title Section */}
      <div className="flex flex-col">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && (
          <p
            className="text-sm text-muted-foreground"
            data-testid="header-subtitle"
          >
            {subtitle}
          </p>
        )}
      </div>

      {/* Search and Actions */}
      <div className="flex items-center gap-4">
        {/* Search */}
        {onSearch && (
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              role="searchbox"
              placeholder="Search books..."
              aria-label="Search books"
              value={searchValue}
              onChange={handleSearchChange}
              className="pl-9"
            />
          </div>
        )}

        {/* Actions */}
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
