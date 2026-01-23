/**
 * AppShell - Main application wrapper with sidebar and sticky player area
 */
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { ConnectedStickyPlayer } from "@/components/domain/ConnectedStickyPlayer";

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
  /** Override default sticky player. Pass `null` to hide the player area entirely. */
  playerContent?: React.ReactNode | null;
  /** Hide the sticky player area (useful for the main player page) */
  hidePlayer?: boolean;
}

export function AppShell({
  children,
  className,
  sidebarProps = {},
  headerProps = { title: "Library" },
  playerContent,
  hidePlayer = false,
}: AppShellProps) {
  // Determine what to render in the player area
  const renderPlayerArea = () => {
    if (hidePlayer || playerContent === null) {
      return null;
    }
    if (playerContent !== undefined) {
      return playerContent;
    }
    // Default: use the connected sticky player
    return <ConnectedStickyPlayer />;
  };

  const playerAreaContent = renderPlayerArea();

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
        {playerAreaContent && (
          <div
            data-testid="player-area"
            className="border-t border-border bg-card"
          >
            {playerAreaContent}
          </div>
        )}
      </div>
    </div>
  );
}
