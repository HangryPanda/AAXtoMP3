/**
 * Settings-related type definitions
 */

export type OutputFormat = "mp3" | "m4a" | "m4b" | "flac" | "opus" | "ogg";

export type MoveFilesPolicy = "report_only" | "always_move" | "ask_each";

export interface Settings {
  output_format: OutputFormat;
  single_file: boolean;
  compression_mp3: number;
  compression_flac: number;
  compression_opus: number;
  cover_size: string;
  dir_naming_scheme: string;
  file_naming_scheme: string;
  chapter_naming_scheme: string;
  no_clobber: boolean;
  move_after_complete: boolean;
  auto_retry: boolean;
  max_retries: number;
  author_override: string;
  keep_author_index: number;
  // Repair settings
  repair_extract_metadata: boolean;
  repair_delete_duplicates: boolean;
  repair_update_manifests: boolean;
  move_files_policy: MoveFilesPolicy;
}

export interface SettingsUpdate {
  output_format?: OutputFormat;
  single_file?: boolean;
  compression_mp3?: number;
  compression_flac?: number;
  compression_opus?: number;
  cover_size?: string;
  dir_naming_scheme?: string;
  file_naming_scheme?: string;
  chapter_naming_scheme?: string;
  no_clobber?: boolean;
  move_after_complete?: boolean;
  auto_retry?: boolean;
  max_retries?: number;
  author_override?: string;
  keep_author_index?: number;
  // Repair settings
  repair_extract_metadata?: boolean;
  repair_delete_duplicates?: boolean;
  repair_update_manifests?: boolean;
  move_files_policy?: MoveFilesPolicy;
}

export interface NamingVariables {
  directory: string[];
  file: string[];
  chapter: string[];
}

// Available naming scheme variables
export const NAMING_VARIABLES: string[] = [
  "$title",
  "$artist",
  "$album_artist",
  "$genre",
  "$narrator",
  "$series",
  "$series_sequence",
  "$year",
];

export const CHAPTER_NAMING_VARIABLES: string[] = [
  ...NAMING_VARIABLES,
  "$chapter",
  "$chapternum",
  "$chaptercount",
];

// Output format options with descriptions
export const OUTPUT_FORMAT_OPTIONS: { value: OutputFormat; label: string; description: string }[] = [
  { value: "m4b", label: "M4B", description: "Audiobook format with chapter support" },
  { value: "m4a", label: "M4A", description: "AAC audio format" },
  { value: "mp3", label: "MP3", description: "Universal audio format" },
  { value: "flac", label: "FLAC", description: "Lossless audio format" },
  { value: "opus", label: "Opus", description: "Modern, efficient format" },
  { value: "ogg", label: "Ogg Vorbis", description: "Open-source format" },
];

// Compression level ranges per format
export const COMPRESSION_RANGES: Record<string, { min: number; max: number; description: string }> = {
  mp3: { min: 0, max: 9, description: "0 = best quality, 9 = fastest" },
  flac: { min: 0, max: 12, description: "0 = fastest, 12 = smallest file" },
  opus: { min: 0, max: 10, description: "0 = fastest, 10 = best quality" },
};

// Cover size options
export const COVER_SIZE_OPTIONS: { value: string; label: string }[] = [
  { value: "500", label: "500px" },
  { value: "1000", label: "1000px" },
  { value: "1215", label: "1215px (Full)" },
];

// Default settings
export const DEFAULT_SETTINGS: Settings = {
  output_format: "m4b",
  single_file: true,
  compression_mp3: 4,
  compression_flac: 5,
  compression_opus: 5,
  cover_size: "1215",
  dir_naming_scheme: "$genre/$artist/$title",
  file_naming_scheme: "$title",
  chapter_naming_scheme: "",
  no_clobber: false,
  move_after_complete: false,
  auto_retry: true,
  max_retries: 3,
  author_override: "",
  keep_author_index: 0,
  // Repair settings
  repair_extract_metadata: true,
  repair_delete_duplicates: false,
  repair_update_manifests: true,
  move_files_policy: "report_only",
};
