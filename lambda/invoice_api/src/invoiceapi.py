from fastapi import FastAPI
from mangum import Mangum
from pydantic import BaseModel

app = FastAPI()


class Invoice(BaseModel):
    invoice_id: int
    amount: float
    tax_amount: float
    is_auto: bool


@app.get("/")
async def root():
    return {"message": "Invoice Management API"}


@app.get("/get-invoice/{invoice_id}")
async def get_invoice(invoice_id: int):
    return {"invoice_id": invoice_id}
