import json
import traceback
from datetime import datetime

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from schema import CustomerSchema
import logging
from dateutil.relativedelta import relativedelta
from fastapi.encoders import jsonable_encoder
from db import (
    does_account_exists_for_customer,
    create_customer_and_account,
    get_account_balance,
    get_dates,
    account_helper,
    get_created_date,
    get_card_limit,
    customer_helper,
    update_balance,
    delete_invalid_cards,
    get_customer_details,
    get_account_details, accounts_collection,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

app = FastAPI(
    title="Banking API",
    version="1.0.0",
    docs_url="/",
    redoc_url="/docs"
)


def ResponseModel(data, status_code, message):
    return {
        "data": [data],
        "code": status_code,
        "message": message,
    }


@app.post("/create_card", response_description="card created successfully")
async def create_account(account_holder_details: CustomerSchema = Body(...)):
    try:
        if await does_account_exists_for_customer(account_holder_details):
            return JSONResponse(status_code=409, content={
                "account_holder_details": jsonable_encoder(account_holder_details),
                "message": f"Customer already has account registered under Aadhaar {account_holder_details.aadhaar}"
            })
        logging.info("Creating Account")
        new_customer, new_account = await create_customer_and_account(jsonable_encoder(account_holder_details))
        logging.info("Created account")
        return JSONResponse(status_code=200, content={
            "account_holder_details": jsonable_encoder(new_customer),
            "account_details": jsonable_encoder(new_account),
            "message": f"Account has been created under Aadhaar {account_holder_details.aadhaar}"
        })
    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()


@app.get("/get_card_details", response_description="Retrieved card details")
async def get_details(account_number: int):
    try:
        account_exists, account = await get_account_details("account_number", account_number)
        if account_exists:
            logging.info("Getting account details from DB")
            aadhaar = account_helper(account)["aadhaar"]
            customer = await get_customer_details(aadhaar)
            return JSONResponse(status_code=200, content={
                "account_details": account_helper(account),
                "customer_details": customer_helper(customer)
            })
        return JSONResponse(status_code=404, content={
            "message": f"Account does not exist with account number {account_number}.Please recheck your account number."
        })
    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "message": f"Error occurred while trying to fetch the account details with account number {account_number}."
        })


@app.get("/get_card_balance", response_description="Retrieved card balance")
async def get_balance(account_number:int):
    try:
        logging.info("Getting card balance from DB")
        account_exists,card_balance = await get_account_balance(account_number)
        if account_exists:
            return JSONResponse(status_code=200, content= card_balance)
        return JSONResponse(status_code=404, content={
            "message": f"Creditcard does not exist with card_number {account_number}.Please recheck your account number."
        })
    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "message": f"Error occurred while trying to fetch the  card_balance with card_number {account_number}."
        })


@app.post("/transact", response_description="card transcation")
async def transact(account_number:int, amount: int, operation_type: str,):
    try:
        account_exists, account = await get_account_details("account_number", account_number)
        if account_exists and account["is_active"] and operation_type=="DEPOSIT":
            available_balance = (account["card_balance"])
            print(type(available_balance))

            if operation_type == "WITHDRA":
                return JSONResponse(status_code=406, content={
                    "message": f"Insufficient funds. Available balance - {available_balance}"
                })
            # # # logging.info(f"Depositing {amount} to {account_number}")
            updated_account_balance = await update_balance(account_number, amount, account_helper(account)["card_balance"],
                                                           operation_type)
            # logging.info(f"Deposited {amount} to {account_number}")
            return JSONResponse(
                status_code=200,
                content={
                    "updated_balance": updated_account_balance,
                    "message": f"{amount} deposited into your card",
                })
        elif not account["is_active"]:
            # logging.info(f"Cannot deposit to de-activated account")
            return JSONResponse(
                status_code=200, content={
                    "message": f"Your account {account_number} is de-activated. Cannot deposit amount now."
                })
        if account_exists and account["is_active"] and operation_type == "WITHDRAW":
            available_balance = (account["card_balance"])
            print(type(available_balance))

            if operation_type == "WITHDRA":
                return JSONResponse(status_code=406, content={
                    "message": f"Insufficient funds. Available balance - {available_balance}"
                })
            # # # logging.info(f"Depositing {amount} to {account_number}")
            updated_account_balance = await update_balance(account_number, amount,account_helper(account)["card_balance"],
                                                               operation_type)
            # logging.info(f"Deposited {amount} to {account_number}")
            return JSONResponse(
                status_code=200,
                content={
                    "updated_balance": updated_account_balance,
                    "message": f"{amount} withdraw from your card",
                })
        elif not account["is_active"]:
            # logging.info(f"Cannot deposit to de-activated account")
            return JSONResponse(
                status_code=200, content={
                    "message": f"Your account {account_number} is de-activated. Cannot deposit amount now."
                })

        return JSONResponse(
            status_code=404, content={
                "message": f"Account does not exist with account number {account_number}."
                           f"Please recheck your account number."
            })


    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "message": f"Error occurred while trying to deposit {amount} to the account with account number "
                       f"{account_number}."
        })
@app.get("/get_card_bill", response_description="card_bill_raised_monthly")
async def get_card_bill(account_number:int):
    try:
        logging.info("Getting card_bill monthly")
        account_exists,card_balance = await get_account_balance(account_number)
        account_exists,card_limit=await get_card_limit(account_number)
        account_exists, created_date = await get_created_date(account_number)
        dateformat = "%d/%m/%Y"
        date = datetime.strptime(created_date,dateformat)
        bill_date = date + relativedelta(days=20)
        deadline_date = bill_date + relativedelta(days=20)

        if date == bill_date:
            balance = json.dumps((int(card_limit)-int(card_balance)),default=int)
            if account_exists:
                return JSONResponse(status_code=200, content= "card_bill:"+str(balance))
            else:
                return JSONResponse(status_code=404, content={
                    "message": f"Creditcard does not exist with card_number {account_number}.Please recheck your account number."
                })
        elif date < bill_date:
            return JSONResponse(status_code=404, content={"message": "bill_date not arrived."})

    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "message": f"Error occurred while trying to fetch the  card_bill with card_number {account_number}."
        })



@app.get("/deactivate_cards")
async def deactivate_cards():
    try:
        logging.info("Deactivating cards")
        deactivated_cards = await delete_invalid_cards()
        logging.info("Deactivated cards")
        return JSONResponse(status_code=200, content={"deactivated_cards": deactivated_cards})
    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500,
                                content={"message": f"Error occurred while soft deleting the accounts"})



@app.post("/payment", response_description="Amount payment")
async def payment_cardbill(account_number:int,operation_type:str):
    try:
        account_exists, card_balance = await get_account_balance(account_number)
        account_exists, card_limit = await get_card_limit(account_number)
        account_exists, account = await get_account_details("account_number", account_number)
        account_exists, created_date = await get_created_date(account_number)
        dateformat = "%d/%m/%Y"
        today=datetime.today().strftime('%d/%m/%Y')
        pay_date=datetime.strptime(today, dateformat)
        c_date = datetime.strptime(created_date, dateformat)
        bill_date = c_date + relativedelta(days=20)
        deadline_date = bill_date + relativedelta(days=20)

        if (bill_date > pay_date) and (deadline_date < pay_date):
            balance = json.dumps((int(card_limit) - int(card_balance)), default=int)
            updated_balance = card_balance+balance

            if account_exists:
                updated_account_balance = await update_balance(account_number, balance,
                                                               account_helper(account)["card_balance"],
                                                               operation_type)
                return JSONResponse(
                status_code=200,
                content={
                    "updated_balance": updated_balance,
                    "message": f"{balance} deposit into your card",
                })
        elif (bill_date > pay_date) and (deadline_date>pay_date):
            balance = json.dumps((int(card_limit) - int(card_balance)), default=int)
            interest= (int(balance)/100) * 2
            paid_amount=int(balance)+int(interest)
            updated_balance = int(card_balance) + int(balance)
            if account_exists:
                updated_account_balance = await update_balance(account_number, balance,
                                                               account_helper(account)["card_balance"],
                                                               operation_type)
                return JSONResponse(
                status_code=200,
                content={
                    "updated_balance": updated_balance,
                    "message": f"{balance} deposit into your card",
                })

    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "message": f"Error occurred while trying to fetch the  card_bill with card_number {account_number}."
        })
