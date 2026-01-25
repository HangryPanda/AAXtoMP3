"use client";

/**
 * Sidebar navigation component
 */
import * as React from "react";
import Link from "next/link";
import { Library, Settings, Briefcase, Headphones, Eye, EyeOff, Wrench, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useJobsFiltered } from "@/hooks/useJobs";
import { useUIStore } from "@/store/uiStore";
import type { JobStatus } from "@/types";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { href: "/library", label: "Library", icon: Library },
  { href: "/settings", label: "Settings", icon: Settings },
];

export interface SidebarProps {
  activePath?: string;
  activeJobCount?: number;
  collapsed?: boolean;
  className?: string;
  onJobsClick?: () => void;
  onTasksClick?: () => void;
  showRepairProgressCard?: boolean;
  onToggleRepairProgressCard?: () => void;
}

export function Sidebar({
  activePath,
  activeJobCount = 0,
  collapsed = false,
  className,
  onJobsClick,
  onTasksClick,
  showRepairProgressCard,
  onToggleRepairProgressCard,
}: SidebarProps) {
  const showRepairToggle = activePath === "/library" && typeof onToggleRepairProgressCard === "function";
  const RepairToggleIcon = showRepairProgressCard ? EyeOff : Eye;

  const clearedBeforeMs = useUIStore((s) => s.progressPopover.clearedBeforeMs);
  const { data: failedJobsData } = useJobsFiltered(
    { status: "FAILED" as JobStatus, limit: 50 },
    { staleTime: 15_000, refetchInterval: 30_000 }
  );
  const failedCount = React.useMemo(() => {
    const items = failedJobsData?.items ?? [];
    if (!clearedBeforeMs) return items.length;
    return items.filter((j) => {
      const t = Date.parse(j.created_at);
      return Number.isFinite(t) && t > clearedBeforeMs;
    }).length;
  }, [clearedBeforeMs, failedJobsData?.items]);

  const taskStatusIcon = React.useMemo(() => {
    if (activeJobCount > 0) {
      return <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />;
    }
    if (failedCount > 0) {
      return <XCircle className="h-5 w-5 shrink-0 text-destructive" />;
    }
    return <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />;
  }, [activeJobCount, failedCount]);

  return (
    <nav
      role="navigation"
      aria-label="Main navigation"
      className={cn(
        "flex flex-col bg-card border-r border-border h-full transition-all duration-300",
        collapsed ? "w-16" : "w-64",
        className
      )}
    >
      {/* Logo */}
      <div className="p-4 border-b border-border">
        <Link
          href="/"
          className="flex items-center gap-2"
          data-testid="sidebar-logo"
        >
          <Headphones className="h-8 w-8 text-primary" />
          {!collapsed && (
            <span className="font-semibold text-lg">Audible Library</span>
          )}
        </Link>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 py-4 px-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePath === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </div>

      {/* Jobs Button */}
      <div className="p-4 border-t border-border">
        <Button
          variant="ghost"
          onClick={onTasksClick}
          disabled={!onTasksClick}
          className={cn(
            "w-full justify-start gap-3 mb-1",
            collapsed && "justify-center px-0"
          )}
          aria-label="Tasks"
        >
          {taskStatusIcon}
          {!collapsed && <span>Tasks</span>}
        </Button>

        {showRepairToggle && (
          <Button
            variant="ghost"
            onClick={onToggleRepairProgressCard}
            className={cn(
              "w-full justify-start gap-3 mb-1",
              collapsed && "justify-center px-0"
            )}
            aria-label={showRepairProgressCard ? "Hide repair status card" : "Show repair status card"}
          >
            <Wrench className="h-5 w-5 shrink-0" />
            {!collapsed && (
              <span className="flex items-center gap-2">
                Repair Status
                <span className="text-xs text-muted-foreground">
                  ({showRepairProgressCard ? "shown" : "hidden"})
                </span>
              </span>
            )}
            <RepairToggleIcon className={cn("h-4 w-4", collapsed ? "" : "ml-auto")} />
          </Button>
        )}

        <Button
          variant="ghost"
          onClick={onJobsClick}
          disabled={!onJobsClick}
          className={cn(
            "w-full justify-start gap-3",
            collapsed && "justify-center px-0"
          )}
          aria-label={`Jobs${activeJobCount > 0 ? ` (${activeJobCount} active)` : ""}`}
        >
          <Briefcase className="h-5 w-5 shrink-0" />
          {!collapsed && <span>Jobs</span>}
          {activeJobCount > 0 && (
            <Badge
              variant="info"
              className="ml-auto"
              data-testid="job-indicator"
            >
              {activeJobCount}
            </Badge>
          )}
        </Button>
      </div>
    </nav>
  );
}
