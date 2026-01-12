

























































































































































































































































#!/bin/bash

# Pi-Autopilot Database Restore Script
# Usage: ./scripts/restore_backup.sh <backup_file>
#
# Restores the SQLite database from a compressed backup file.
# This is used in disaster recovery scenarios.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Example:"
    echo "  ./scripts/restore_backup.sh data/artifacts/backups/pipeline_db_2026-01-12T143022.sqlite.gz"
    echo ""
    exit 1
fi

BACKUP_FILE="$1"
DB_PATH="$PROJECT_ROOT/data/pipeline.db"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "========================================="
echo "Pi-Autopilot Database Restore Script"
echo "========================================="
echo ""
echo "Backup file: $BACKUP_FILE"
echo "Target DB:   $DB_PATH"
echo ""

# Check if current database exists and create a safety backup
if [ -f "$DB_PATH" ]; then
    SAFETY_BACKUP="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Current database exists. Creating safety backup..."
    cp "$DB_PATH" "$SAFETY_BACKUP"
    echo "  Safety backup created: $SAFETY_BACKUP"
    echo ""
fi

echo "Restoring database from backup..."
cd "$PROJECT_ROOT"

# Create venv activation for Python execution
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python3"
fi

# Run the restore operation
"$PYTHON" -c "
from services.backup_manager import BackupManager
import sys

try:
    manager = BackupManager('$DB_PATH')
    result = manager.restore_database('$BACKUP_FILE')
    
    if result['success']:
        print('')
        print('✓ Database restored successfully!')
        print(f'  Restored from: $BACKUP_FILE')
        print(f'  Restored to:   $DB_PATH')
        print(f'  Timestamp:     {result.get(\"timestamp\", \"N/A\")}')
        sys.exit(0)
    else:
        print('')
        print('✗ Restore failed: Invalid backup file or corruption detected')
        print('  The safety backup remains available if one was created')
        sys.exit(1)
except Exception as e:
    print('')
    print(f'✗ Restore failed with error: {e}')
    print('  The safety backup remains available if one was created')
    sys.exit(1)
"

RESTORE_EXIT=$?

if [ $RESTORE_EXIT -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "Restore complete. Verify the restored data:"
    echo "========================================="
    echo ""
    echo "  1. Check pipeline status:"
    "$PYTHON" -c "from services.storage import Storage; s = Storage(); posts = s.get_unprocessed_posts(); print(f'   Unprocessed posts: {len(posts)}')"
    echo ""
    echo "  2. Run a test pipeline:"
    echo "   cd $PROJECT_ROOT && python main.py"
    echo ""
    exit 0
else
    echo ""
    echo "========================================="
    echo "Restore FAILED"
    echo "========================================="
    if [ -n "$SAFETY_BACKUP" ]; then
        echo ""
        echo "To restore the previous database state:"
        echo "  gunzip < $SAFETY_BACKUP > $DB_PATH"
    fi
    exit 1
fi
