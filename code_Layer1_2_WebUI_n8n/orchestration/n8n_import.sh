#!/bin/sh
IMPORT_FILE="/import/property_triage_workflow.json"
MARKER="/home/node/.n8n/.property_triage_workflow_imported"

if [ -f "$IMPORT_FILE" ] && [ ! -f "$MARKER" ]; then
  echo "Importing n8n workflow from $IMPORT_FILE"
  n8n import:workflow --input="$IMPORT_FILE"
  touch "$MARKER"
fi

exec n8n start
