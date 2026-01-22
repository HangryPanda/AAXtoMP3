export interface Book {
  asin: string;              // Primary Key
  title: string;
  author: string;
  narrator?: string;
  series?: {
    title: string;
    sequence?: string;
  };
  duration: number;          // Seconds
  coverUrl: string;
  purchaseDate: string;      // ISO Date
  status: "NEW" | "DOWNLOADING" | "DOWNLOADED" | "CONVERTED" | "FAILED";
  files?: {
    aax?: string;            // Absolute path
    m4b?: string;            // Absolute path
  };
}

export interface LogMessage {
  jobId: string;
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR" | "PROGRESS";
  payload: string | number; // String for logs, 0-100 number for PROGRESS
}

export interface Job {
  id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  bookAsin: string;
  type: "DOWNLOAD" | "CONVERT";
  progress: number;
}
