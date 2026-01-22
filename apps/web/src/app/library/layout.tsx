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
  
  return (
    <AppShell
      sidebarProps={{
        activePath: pathname,
        activeJobCount: activeJobs?.total ?? 0,
        onJobsClick: () => setJobDrawerOpen(true),
      }}
      headerProps={{
        title: "Library",
      }}
    >
      {children}
    </AppShell>
  );
}
