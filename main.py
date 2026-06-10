from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException

from splitwise_client import Splitwise
from processor import process, build_shares

app = FastAPI(title="Splitwise Voice")
sw = Splitwise()


@app.get("/groups")
def list_groups():
    return [{"id": g["id"], "name": g["name"]} for g in sw.groups()]


async def _run(image: UploadFile, audio: UploadFile, group_id: int):
    img_bytes   = await image.read()
    audio_bytes = await audio.read()
    members     = sw.members(group_id)
    me          = sw.current_user()
    transcript, receipt, split = process(
        img_bytes, image.filename or "receipt.jpg",
        audio_bytes, audio.filename or "note.m4a",
        members,
    )
    shares = build_shares(split, members, payer_id=me["id"])
    payer = {"id": me["id"], "name": (me.get("first_name", "") + " " + (me.get("last_name") or "")).strip()}
    return transcript, receipt, split, shares, payer


@app.post("/preview")
async def preview(
    image:    UploadFile = File(...),
    audio:    UploadFile = File(...),
    group_id: int        = Form(...),
):
    try:
        transcript, receipt, split, shares, payer = await _run(image, audio, group_id)
    except Exception as e:
        raise HTTPException(400, str(e))
    return {
        "transcript": transcript,
        "receipt":    receipt,    # OCR output — useful for debugging
        "split":      split,
        "shares":     shares,
        "payer":      payer,
    }


@app.post("/process-bill")
async def process_bill(
    image:    UploadFile = File(...),
    audio:    UploadFile = File(...),
    group_id: int        = Form(...),
):
    try:
        transcript, receipt, split, shares, payer = await _run(image, audio, group_id)
        expense = sw.create_expense(
            group_id=group_id,
            description=split.get("description", receipt.get("restaurant", "Bill")),
            cost=float(split["grand_total"]),
            shares=shares,
            currency=split.get("currency", "INR"),
        )
    except Exception as e:
        raise HTTPException(400, str(e))
    return {
        "transcript": transcript,
        "split":      split,
        "expense_id": expense["id"],
        "url":        f"https://secure.splitwise.com/expenses/{expense['id']}",
    }