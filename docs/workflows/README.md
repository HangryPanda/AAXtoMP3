# Application Workflows

This directory contains detailed documentation for the core business logic and data workflows of the Audible Library application, organized by domain.

## [Library Workflows](./library/README.md)
Workflows related to data acquisition, processing, and maintenance.
- Download, Conversion, Metadata Scanning, Library Sync, Repair, and Progress Monitoring.

## [Player Workflows](./player/README.md)
Workflows related to audio playback, streaming, and state persistence.
- Initialization, Playback Controls, Progress Sync, JIT Streaming, and UI Components.

## Architecture Overview
The system uses a **Job-Based Architecture**:
1.  Requests are received via the REST API.
2.  Jobs are queued in the `JobManager`.
3.  Asynchronous workers execute the logic using specialized Services (`AudibleClient`, `ConverterEngine`, `LibraryManager`).
4.  State is persisted to the **PostgreSQL Database** and backed up to **JSON Manifests**.
5.  Real-time updates are pushed to the frontend via **WebSockets** and monitored via the **ProgressPopover**.
