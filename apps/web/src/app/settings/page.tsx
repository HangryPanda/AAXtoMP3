"use client";

import { useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { Save, RotateCcw, HelpCircle, Loader2 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { useActiveJobs } from "@/hooks/useJobs";
import { useResetSettings, useSettings, useUpdateSettings } from "@/hooks/useSettings";
import { useUIStore } from "@/store/uiStore";
import type { OutputFormat, Settings, SettingsUpdate } from "@/types/settings";
import {
  OUTPUT_FORMAT_OPTIONS,
  COMPRESSION_RANGES,
  COVER_SIZE_OPTIONS,
  NAMING_VARIABLES,
  CHAPTER_NAMING_VARIABLES,
  DEFAULT_SETTINGS,
} from "@/types/settings";
import { Button } from "@/components/ui/Button";

export default function SettingsPage() {
  const pathname = usePathname();
  const { data: activeJobs } = useActiveJobs();
  const updateSettingsMutation = useUpdateSettings();
  const resetSettingsMutation = useResetSettings();
  const addToast = useUIStore((state) => state.addToast);
  const setJobDrawerOpen = useUIStore((state) => state.setJobDrawerOpen);

  const { data: remoteSettings, isLoading } = useSettings();
  const [draft, setDraft] = useState<SettingsUpdate>({});

  const hasChanges = useMemo(() => Object.keys(draft).length > 0, [draft]);

  const settings: Settings = useMemo(() => {
    return {
      ...(remoteSettings ?? DEFAULT_SETTINGS),
      ...draft,
    };
  }, [remoteSettings, draft]);

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    const baselineValue = (remoteSettings ?? DEFAULT_SETTINGS)[key];
    setDraft((prev) => {
      if (Object.is(baselineValue, value)) {
        const next = { ...prev } as Record<string, unknown>;
        delete next[key as string];
        return next as SettingsUpdate;
      }
      return { ...prev, [key]: value } as SettingsUpdate;
    });
  };

  const handleSave = async () => {
    if (!hasChanges) return;
    try {
      await updateSettingsMutation.mutateAsync(draft);
      addToast({
        type: "success",
        title: "Settings saved",
        message: "Your preferences have been updated successfully.",
      });
      setDraft({});
    } catch (error) {
      addToast({
        type: "error",
        title: "Failed to save",
        message: error instanceof Error ? error.message : "An unexpected error occurred.",
      });
    }
  };

  const handleReset = async () => {
    if (window.confirm("Are you sure you want to reset all settings to defaults?")) {
      try {
        await resetSettingsMutation.mutateAsync();
        setDraft({});
        addToast({
          type: "info",
          title: "Settings reset",
          message: "Preferences have been restored to defaults.",
        });
      } catch (error) {
        addToast({
          type: "error",
          title: "Reset failed",
          message: error instanceof Error ? error.message : "An unexpected error occurred.",
        });
      }
    }
  };

  if (isLoading && !remoteSettings) {
    return (
      <AppShell 
        sidebarProps={{ 
          activePath: pathname, 
          activeJobCount: activeJobs?.total ?? 0,
          onJobsClick: () => setJobDrawerOpen(true),
        }}
        headerProps={{ title: "Settings" }}
      >
        <div className="flex items-center justify-center h-full">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      sidebarProps={{ 
        activePath: pathname, 
        activeJobCount: activeJobs?.total ?? 0,
        onJobsClick: () => setJobDrawerOpen(true),
      }}
      headerProps={{ 
        title: "Settings",
        actions: (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              className="gap-2"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!hasChanges || updateSettingsMutation.isPending}
              className="gap-2"
            >
              {updateSettingsMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Changes
            </Button>
          </div>
        )
      }}
    >
      <div className="max-w-3xl mx-auto space-y-8 pb-10">
        {/* Output Format Section */}
        <section className="bg-card border border-border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Output Format</h2>

          <div className="grid gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">Primary Format</label>
              <select
                value={settings.output_format}
                onChange={(e) => updateSetting("output_format", e.target.value as OutputFormat)}
                className="w-full h-10 px-3 py-2 bg-background rounded-md border border-input focus:ring-2 focus:ring-ring focus:outline-none"
              >
                {OUTPUT_FORMAT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label} — {option.description}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="single_file"
                checked={settings.single_file}
                onChange={(e) => updateSetting("single_file", e.target.checked)}
                className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
              />
              <label htmlFor="single_file" className="text-sm font-medium leading-none cursor-pointer">
                Single file output (do not split into chapters)
              </label>
            </div>

            {/* Compression settings based on format */}
            {settings.output_format === "mp3" && (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <label className="text-sm font-medium">
                    MP3 Compression Level
                  </label>
                  <span className="text-sm text-muted-foreground font-mono bg-muted px-2 py-0.5 rounded">
                    Level {settings.compression_mp3}
                  </span>
                </div>
                <input
                  type="range"
                  min={COMPRESSION_RANGES.mp3.min}
                  max={COMPRESSION_RANGES.mp3.max}
                  value={settings.compression_mp3}
                  onChange={(e) => updateSetting("compression_mp3", parseInt(e.target.value))}
                  className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <p className="text-xs text-muted-foreground italic">
                  {COMPRESSION_RANGES.mp3.description}
                </p>
              </div>
            )}

            {(settings.output_format === "flac" || settings.output_format === "opus") && (
               <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <label className="text-sm font-medium">
                    {settings.output_format.toUpperCase()} Compression Level
                  </label>
                  <span className="text-sm text-muted-foreground font-mono bg-muted px-2 py-0.5 rounded">
                    Level {settings.output_format === "flac" ? settings.compression_flac : settings.compression_opus}
                  </span>
                </div>
                <input
                  type="range"
                  min={settings.output_format === "flac" ? COMPRESSION_RANGES.flac.min : COMPRESSION_RANGES.opus.min}
                  max={settings.output_format === "flac" ? COMPRESSION_RANGES.flac.max : COMPRESSION_RANGES.opus.max}
                  value={settings.output_format === "flac" ? settings.compression_flac : settings.compression_opus}
                  onChange={(e) => updateSetting(settings.output_format === "flac" ? "compression_flac" : "compression_opus", parseInt(e.target.value))}
                  className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                />
              </div>
            )}
          </div>
        </section>

        {/* Download Settings */}
        <section className="bg-card border border-border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Download Settings</h2>

          <div className="grid gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">Cover Image Size</label>
              <select
                value={settings.cover_size}
                onChange={(e) => updateSetting("cover_size", e.target.value)}
                className="w-full h-10 px-3 py-2 bg-background rounded-md border border-input focus:ring-2 focus:ring-ring focus:outline-none"
              >
                {COVER_SIZE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Naming Schemes */}
        <section className="bg-card border border-border rounded-lg p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">Naming Schemes</h2>
            <HelpCircle className="w-4 h-4 text-muted-foreground cursor-help" />
          </div>

          <div className="grid gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">Directory Pattern</label>
              <input
                type="text"
                value={settings.dir_naming_scheme}
                onChange={(e) => updateSetting("dir_naming_scheme", e.target.value)}
                className="w-full h-10 px-3 py-2 bg-background rounded-md border border-input font-mono text-sm focus:ring-2 focus:ring-ring focus:outline-none"
              />
              <div className="flex flex-wrap gap-1.5 pt-1">
                {NAMING_VARIABLES.map((v) => (
                  <button 
                    key={v} 
                    type="button"
                    onClick={() => updateSetting("dir_naming_scheme", settings.dir_naming_scheme + v)}
                    className="px-2 py-1 bg-secondary hover:bg-secondary/80 rounded text-[10px] font-mono transition-colors"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">File Name Pattern</label>
              <input
                type="text"
                value={settings.file_naming_scheme}
                onChange={(e) => updateSetting("file_naming_scheme", e.target.value)}
                className="w-full h-10 px-3 py-2 bg-background rounded-md border border-input font-mono text-sm focus:ring-2 focus:ring-ring focus:outline-none"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Chapter Naming Pattern (if splitting)</label>
              <input
                type="text"
                value={settings.chapter_naming_scheme}
                onChange={(e) => updateSetting("chapter_naming_scheme", e.target.value)}
                placeholder="Leave empty for default"
                className="w-full h-10 px-3 py-2 bg-background rounded-md border border-input font-mono text-sm focus:ring-2 focus:ring-ring focus:outline-none"
              />
              <div className="flex flex-wrap gap-1.5 pt-1">
                {CHAPTER_NAMING_VARIABLES.filter((v) => !NAMING_VARIABLES.includes(v)).map((v) => (
                  <button 
                    key={v} 
                    type="button"
                    onClick={() => updateSetting("chapter_naming_scheme", settings.chapter_naming_scheme + v)}
                    className="px-2 py-1 bg-secondary hover:bg-secondary/80 rounded text-[10px] font-mono transition-colors"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Automation & Behavior */}
        <section className="bg-card border border-border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Automation & Behavior</h2>

          <div className="space-y-4">
             <div className="flex items-start space-x-3 p-3 rounded-md hover:bg-muted/50 transition-colors cursor-pointer">
              <input
                type="checkbox"
                id="no_clobber"
                checked={settings.no_clobber}
                onChange={(e) => updateSetting("no_clobber", e.target.checked)}
                className="h-4 w-4 mt-1 rounded border-input text-primary focus:ring-ring"
              />
              <div className="grid gap-1.5 leading-none">
                <label htmlFor="no_clobber" className="text-sm font-medium leading-none cursor-pointer">No Clobber</label>
                <p className="text-xs text-muted-foreground">Skip conversion if the target file already exists on disk.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 rounded-md hover:bg-muted/50 transition-colors cursor-pointer">
              <input
                type="checkbox"
                id="move_after_complete"
                checked={settings.move_after_complete}
                onChange={(e) => updateSetting("move_after_complete", e.target.checked)}
                className="h-4 w-4 mt-1 rounded border-input text-primary focus:ring-ring"
              />
               <div className="grid gap-1.5 leading-none">
                <label htmlFor="move_after_complete" className="text-sm font-medium leading-none cursor-pointer">Cleanup Source</label>
                <p className="text-xs text-muted-foreground">Move AAX/AAXC files to a &apos;completed&apos; subfolder after successful conversion.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 rounded-md hover:bg-muted/50 transition-colors cursor-pointer">
              <input
                type="checkbox"
                id="auto_retry"
                checked={settings.auto_retry}
                onChange={(e) => updateSetting("auto_retry", e.target.checked)}
                className="h-4 w-4 mt-1 rounded border-input text-primary focus:ring-ring"
              />
               <div className="grid gap-1.5 leading-none">
                <label htmlFor="auto_retry" className="text-sm font-medium leading-none cursor-pointer">Auto Retry</label>
                <p className="text-xs text-muted-foreground">Automatically retry failed downloads or conversions up to max attempts.</p>
              </div>
            </div>

            {settings.auto_retry && (
              <div className="ml-10 pt-2 flex items-center gap-4">
                <label className="text-sm font-medium">Max Retry Attempts</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={settings.max_retries}
                  onChange={(e) => updateSetting("max_retries", parseInt(e.target.value))}
                  className="w-20 h-10 px-3 py-2 bg-background rounded-md border border-input focus:ring-2 focus:ring-ring focus:outline-none"
                />
              </div>
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
