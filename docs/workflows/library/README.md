# Library Workflows

This directory contains documentation for workflows related to library management, data acquisition, and processing.

## Processing Workflows
- **[Download](./download_workflow.md)**: File retrieval from Audible (AAX/AAXC and Vouchers).
- **[Conversion](./conversion_workflow.md)**: Decryption and transcoding pipeline.
- **[Metadata & Scanning](./metadata_workflow.md)**: Deep scanning of media files for chapters and technical data.

## Sync & Maintenance
- **[Library Sync](./library_sync_workflow.md)**: Synchronizing basic metadata from the Audible API.
- **[Repair & Reconcile](./repair_workflow.md)**: Reconstructing state from manifests and filesystem.

## User Interface
- **[Progress Popover](./progress_popover_workflow.md)**: Real-time monitoring and control of background tasks.

## Implementation Plans (Agent Work)

These are strict, agent-executable plans with checkpointing and evidence logs:

- **[Conversion Hardening Plan](./conversion_workflow_hardening_plan.md)**
- **[Conversion Hardening Status/Evidence](./conversion_workflow_hardening_status.md)**
- **[Repair Hardening Plan](./repair_workflow_hardening_plan.md)**
- **[Repair Hardening Status/Evidence](./repair_workflow_hardening_status.md)**
