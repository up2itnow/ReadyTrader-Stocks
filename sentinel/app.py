from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from signing import get_signer
from signing.intents import build_evm_tx_intent
from signing.policy import SignerPolicyViolation

app = FastAPI(title="Sentinel Signer", version="1.0.0")

class SignRequest(BaseModel):
    tx: Dict[str, Any]
    chain_id: Optional[int] = None
    intent: Optional[Dict[str, Any]] = None

@app.get("/address")
def get_address():
    signer = get_signer()
    return {"address": signer.get_address()}

@app.post("/sign_transaction")
def sign_transaction(req: SignRequest):
    try:
        signer = get_signer()
        # "Firewall" Logic: verify intent matches tx
        if req.intent:
            calculated_intent = build_evm_tx_intent(req.tx, chain_id=req.chain_id)
            if calculated_intent.to_dict() != req.intent:
                raise HTTPException(status_code=400, detail="Intent mismatch: payload does not match declared intent.")
        
        signed = signer.sign_transaction(req.tx, chain_id=req.chain_id)
        return {"rawTransactionHex": "0x" + signed.rawTransaction.hex()}
    except SignerPolicyViolation as e:
        raise HTTPException(status_code=403, detail=f"Policy violation: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
