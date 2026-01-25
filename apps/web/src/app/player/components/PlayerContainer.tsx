import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { getCoverUrl, getPrimaryAuthor } from "@/types";
import { useUIStore } from "@/store/uiStore";
import { usePlayerLogic } from "../hooks/usePlayerLogic";
import { DesktopPlayerLayout } from "../layouts/DesktopPlayerLayout";
import {
  MetadataModal,
  SleepTimerModal,
  ShortcutsModal,
  SeriesModal,
  ConflictModal,
} from "./modals";

export function PlayerContainer() {
  const router = useRouter();
  const logic = usePlayerLogic();
  const openProgressPopover = useUIStore((s) => s.openProgressPopover);
  
  // Modals state
  const [showMetadataModal, setShowMetadataModal] = useState(false);
  const [showSleepTimerModal, setShowSleepTimerModal] = useState(false);
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [showSeriesModal, setShowSeriesModal] = useState(false);
  const [showPositionConflictModal, setShowPositionConflictModal] = useState(false);

  // Auto-open logic
  if (logic.positionConflict && !showPositionConflictModal) {
    setShowPositionConflictModal(true);
  }

  // Conflict handlers
  const handleUseServerPosition = () => {
    if (logic.positionConflict) {
      logic.seek(logic.positionConflict.serverTime);
    }
    setShowPositionConflictModal(false);
    logic.setPositionConflict(null);
  };

  const handleUseLocalPosition = () => {
    if (logic.positionConflict) {
      logic.seek(logic.positionConflict.localTime);
    }
    setShowPositionConflictModal(false);
    logic.setPositionConflict(null);
  };

  // Derived display data
  const title = logic.localItem?.title ?? logic.book?.title ?? "Select a Book";
  const author = logic.localItem?.authors ?? (logic.book ? getPrimaryAuthor(logic.book) : "Unknown Author");
  const coverUrl = logic.book ? getCoverUrl(logic.book, "1215") : null;

  return (
    <AppShell
      sidebarProps={{
        activeJobCount: logic.activeJobs?.total ?? 0,
        activePath: "/player",
        onJobsClick: () => logic.setJobDrawerOpen(true),
        onTasksClick: () => openProgressPopover("history"),
      }}
      headerProps={{
        title: "Now Playing",
      }}
      hidePlayer
    >
      <DesktopPlayerLayout
        logic={logic}
        onBack={() => router.push("/library")}
        coverUrl={coverUrl}
        title={title}
        author={author}
        showModals={{
          metadata: () => setShowMetadataModal(true),
          sleepTimer: () => setShowSleepTimerModal(true),
          shortcuts: () => setShowKeyboardShortcuts(true),
          series: () => setShowSeriesModal(true),
          cancelSleepTimer: logic.cancelSleepTimer,
        }}
      />

      {/* Modals */}
      <MetadataModal
        open={showMetadataModal}
        onOpenChange={setShowMetadataModal}
        book={logic.book}
        localItem={logic.localItem}
        bookDetails={logic.bookDetails}
        duration={logic.duration}
      />

      <SleepTimerModal
        open={showSleepTimerModal}
        onOpenChange={setShowSleepTimerModal}
        onSetTimer={logic.handleSleepTimer}
      />

      <ShortcutsModal
        open={showKeyboardShortcuts}
        onOpenChange={setShowKeyboardShortcuts}
      />

      <SeriesModal
        open={showSeriesModal}
        onOpenChange={setShowSeriesModal}
        nextInSeries={logic.nextInSeries}
        onPlayNext={logic.handlePlayNextInSeries}
      />

      <ConflictModal
        open={showPositionConflictModal}
        onOpenChange={setShowPositionConflictModal}
        conflict={logic.positionConflict}
        onUseServer={handleUseServerPosition}
        onUseLocal={handleUseLocalPosition}
      />
    </AppShell>
  );
}
