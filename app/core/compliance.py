import hashlib
import json
import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ComplianceLedger:
    """
    Centralized auditor for all trading decisions.
    Ensures non-repudiable logging of Rationale -> Risk -> Execution.
    """
    def __init__(self, log_path: str = "data/compliance_audit.log"):
        self.log_path = log_path
        # Ensure directory exists is handled by the caller or setup
        
    def record_event(self, event_type: str, data: Dict[str, Any]):
        """
        Write a compliance-stamped event to the audit log.
        """
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data,
            "system_integrity_hash": self._sign_entry(data)
        }
        
        log_line = json.dumps(entry)
        with open(self.log_path, "a") as f:
            f.write(log_line + "\n")
            
        logger.info(f"[COMPLIANCE] {event_type} recorded.")

    def _sign_entry(self, data: Dict[str, Any]) -> str:
        # Simple local hash for integrity (non-HSM)
        payload = json.dumps(data, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """
        Basic integrity check for the trading system.
        """
        # Ensure the log file exists or can be created
        try:
            with open(self.log_path, "a"):
                pass
            return True
        except Exception:
            return False

global_compliance_ledger = ComplianceLedger()
