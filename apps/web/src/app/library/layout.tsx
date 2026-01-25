"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { useActiveJobs } from "@/hooks/useJobs";
import { useUIStore } from "@/store/uiStore";

export default function LibraryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { data: activeJobs } = useActiveJobs();
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);
  const openProgressPopover = useUIStore((s) => s.openProgressPopover);
  const isRepairProgressCardVisible = useUIStore((s) => s.isRepairProgressCardVisible);
  const toggleRepairProgressCardVisible = useUIStore((s) => s.toggleRepairProgressCardVisible);
  
  return (
    <AppShell
      sidebarProps={{
        activePath: pathname,
        activeJobCount: activeJobs?.total ?? 0,
        onJobsClick: () => setJobDrawerOpen(true),
        onTasksClick: () => openProgressPopover("history"),
        showRepairProgressCard: isRepairProgressCardVisible,
        onToggleRepairProgressCard: toggleRepairProgressCardVisible,
      }}
      headerProps={{
        title: "Library",
      }}
    >
      {children}
    </AppShell>
  );
}
