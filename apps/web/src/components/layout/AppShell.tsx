/**
 * AppShell - Main application wrapper with sidebar and sticky player area
 */
import * as React from "react";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export interface AppShellProps {
  children: React.ReactNode;
  className?: string;
  sidebarProps?: {
    activePath?: string;
    activeJobCount?: number;
    collapsed?: boolean;
    onJobsClick?: () => void;
  };
  headerProps?: {
    title?: string;
    subtitle?: string;
    searchValue?: string;
    onSearch?: (value: string) => void;
    actions?: React.ReactNode;
  };
  playerContent?: React.ReactNode;
}

export function AppShell({
  children,
  className,
  sidebarProps = {},
  headerProps = { title: "Library" },
  playerContent,
}: AppShellProps) {
  return (
    <div
      data-testid="app-shell"
      className={cn("flex h-screen overflow-hidden bg-background", className)}
    >
      {/* Sidebar */}
      <Sidebar {...sidebarProps} />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <Header {...headerProps} />

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-6">{children}</main>

        {/* Sticky Player Area */}
        <div
          data-testid="player-area"
          className="border-t border-border bg-card"
        >
          {playerContent || (
            <div className="h-20 flex items-center justify-center text-muted-foreground">
              No track playing
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
