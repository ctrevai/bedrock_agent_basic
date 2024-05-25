from typing import Optional
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from mangum import Mangum
from pydantic import BaseModel
import time
import os
import boto3
from boto3.dynamodb.conditions import Key

app = FastAPI(root_path="/prod")
handler = Mangum(app)


class PutInvoice(BaseModel):
    invoice_id: str
    user_id: Optional[str] = None
    amount: str
    is_auto: bool = False


@app.get("/")
async def root():
    return {"message": "Invoice Management API"}

# create invoice


@app.post("/create-invoice")
async def create_invoice(put_invoice: PutInvoice):
    created_time = int(time.time())
    invoice = {
        "invoice_id": f"invoice_{uuid4().hex}",  # put_invoice.invoice_id,
        "user_id": put_invoice.user_id,
        "amount": put_invoice.amount,
        "is_auto": put_invoice.is_auto,
        "created_time": created_time,
        "ttl": int(created_time + 86400),  # 24 hours
    }

    table = _get_table()
    table.put_item(Item=invoice)
    return {"invoice": invoice}

# get invoice by invoice_id


@app.get("/get-invoice/{invoice_id}")
async def get_invoice(invoice_id: str):
    table = _get_table()
    response = table.get_item(Key={"invoice_id": invoice_id})
    invoice = response.get("Item")
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {
                            invoice_id} not found")
    return invoice

# list invoices


@app.get("/list-invoices/{user_id}")
async def list_invoices(user_id: str):
    table = _get_table()
    response = table.query(
        IndexName="user-index",
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
        Limit=10,
    )
    invoices = response.get("Items")
    print(invoices)
    return {"invoices": invoices}

# update invoice


@app.put("/update-invoice/")
async def update_invoice(put_invoice: PutInvoice):
    table = _get_table()
    table.update_item(
        Key={"invoice_id": put_invoice.invoice_id},
        UpdateExpression="set amount = :amount, is_auto = :is_auto",
        ExpressionAttributeValues={
            ":amount": put_invoice.amount,
            ":is_auto": put_invoice.is_auto
        },
        ReturnValues="ALL_NEW"
    )
    return {"updated_invoice_id": put_invoice.invoice_id}

# delete invoice


@app.delete("/delete-invoice/{invoice_id}")
async def delete_invoice(invoice_id: str):
    table = _get_table()
    table.delete_item(Key={"invoice_id": invoice_id})
    return {"deleted_invoice_id": invoice_id}


def _get_table():
    table_name = os.environ.get('TABLE_NAME')
    return boto3.resource('dynamodb').Table(table_name)
