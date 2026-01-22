/**
 * Sidebar navigation component
 */
import * as React from "react";
import Link from "next/link";
import { Library, Settings, Briefcase, Headphones } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

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
}

export function Sidebar({
  activePath,
  activeJobCount = 0,
  collapsed = false,
  className,
  onJobsClick,
}: SidebarProps) {
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
          onClick={onJobsClick}
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
