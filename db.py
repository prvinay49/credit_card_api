import motor.motor_asyncio
import urllib.parse
from schema import CustomerSchema, AccountSchema
from datetime import date, datetime
from utility import random_with_N_digits,limit_with_n_digits
from fastapi.encoders import jsonable_encoder
from dateutil.relativedelta import relativedelta
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

username = urllib.parse.quote_plus('prvinay49')
password = urllib.parse.quote_plus("@9849450903")

MONGO_DETAILS = "mongodb+srv://{}:{}@cluster0.soqhg.mongodb.net/myFirstDatabase?retryWrites=true&w=majority".format(
    username, password)

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)

database = client.bankdb

accounts_collection = database.get_collection("accounts_collection")
customers_collection = database.get_collection("customers_collection")


def customer_helper(customer) -> dict:
    return {
        "account_holder_name": customer["account_holder_name"],
        "aadhaar": customer["aadhaar"],
        "contact": customer["contact"],
        "email": customer["email"],
        "pan": customer["pan"],
        "address": customer["address"],
        "dob": customer["dob"],
    }


def account_helper(account) -> dict:
    return {
        "creditcard_number": account["account_number"],
        "created_date": account["created_date"],
        "bank_name": account["bank_name"],
        "card_type": account["card_type"],
        "last_activity": account["last_activity"],
        "is_active": account["is_active"],
        "aadhaar":account["aadhaar"],
        "exp_date":account["exp_date"],
        "card_limit":account["card_limit"],
        "card_balance": account["card_balance"]
    }


async def does_account_exists_for_customer(customer_details: CustomerSchema):
    existing_customer = await accounts_collection.find_one({"aadhaar": customer_details.aadhaar})
    logging.info(f"{existing_customer}")
    if existing_customer:
        return True
    return False


async def get_account_details(search_key: str, search_value: str):
    account = await accounts_collection.find_one({search_key: search_value})
    logging.info(f"Account details - {account}")
    if account:
        return True, account
    return False, None


async def get_customer_details(aadhaar: str):
    customer = await customers_collection.find_one({"aadhaar": aadhaar})
    logging.info(f"Customer - {customer}")
    if customer:
        return customer
    return None


async def create_customer_and_account(customer_details: CustomerSchema):
    card_details = AccountSchema()
    card_details.aadhaar = customer_details["aadhaar"]
    today = date.today()
    card_details.created_date = today.strftime("%d/%m/%Y")
    card_details.bank_name = "QWERTY"
    card_details.card_type = "Platinum"


    now = datetime.now()
    last_activity = now.strftime("%d/%m/%Y %H:%M:%S")
    
    expiry_date = today+relativedelta(years=7)

    card_details.last_activity = last_activity
    card_details.is_active = True
    card_details.exp_date= expiry_date
    print(expiry_date)

    

    account_number_temp = int(random_with_N_digits(16))
    existing_account_numbers = set()

    card_limit_temp = int(limit_with_n_digits(5))

    async for account in accounts_collection.find():
        if "account_number" in account:
            existing_account_numbers.add(account["account_number"])

    while account_number_temp in existing_account_numbers:
        account_number_temp = int(random_with_N_digits(16))
        card_limit_temp = int(limit_with_n_digits(5))

    card_details.account_number = account_number_temp
    card_details.card_limit = card_limit_temp
    card_details.card_balance = card_limit_temp

    new_customer = await customers_collection.insert_one(customer_details)
    new_account = await accounts_collection.insert_one(jsonable_encoder(card_details))

    new_customer = await customers_collection.find_one({"_id": new_customer.inserted_id})
    new_account = await accounts_collection.find_one({"_id": new_account.inserted_id})

    return customer_helper(new_customer), account_helper(new_account)


async def get_account_balance(account_number: str):
    account_exists, account = await get_account_details("account_number", account_number)
    if account_exists:
          await update_last_activity(account_number)
          return True,account["card_balance"]
    return False, 0

async def get_card_limit(account_number: str):
    account_exists, account = await get_account_details("account_number", account_number)
    if account_exists:
          await update_last_activity(account_number)
          return True,account["card_limit"]
    return False, 0
async def get_created_date(account_number: str):
    account_exists, account = await get_account_details("account_number", account_number)
    if account_exists:
          await update_last_activity(account_number)
          return True,account["created_date"]
    return False, 0

async def update_balance(account_number: str, amount:int, available_balance:int, operation_type: str):
    query = {'account_number': account_number}

    if operation_type == "DEPOSIT":
        updated_balance = {"$set": {"card_balance": int(available_balance) + int(amount)}}
        await accounts_collection.update_one(query, updated_balance)
        updated_balance = await get_account_balance(account_number)
        logging.info("Account balance after updating balance - ", updated_balance[1])
    if operation_type == "WITHDRAW":
        updated_balance = {"$set": {"card_balance": int(available_balance) - int(amount)}}
        print(query)
        await accounts_collection.update_one(query, updated_balance)
        updated_balance = await get_account_balance(account_number)
        logging.info(f"Account balance after withdrawing {amount} - ", updated_balance[1])

    await update_last_activity(account_number)
    return updated_balance[1]


async def update_last_activity(account_number: str):
    query = {"account_number": account_number}
    now = datetime.now()
    last_activity = now.strftime("%d/%m/%Y %H:%M:%S")
    updated_activity = {"$set": {'last_activity': last_activity}}
    await accounts_collection.update_one(query, updated_activity)


async def delete_invalid_cards():
    deactivated_accounts = list()
    async for account in accounts_collection.find():
        card_created_date = account["created_date"]
        date_format = "%d/%m/%Y"
        card_created_date = datetime.strptime(card_created_date, date_format)
        exp_date = card_created_date + relativedelta(years=7)

        if card_created_date == exp_date:
            account_number = account["account_number"]
            is_account_active = account["is_active"]
            query = {"account_number": account_number}
            update_query = {"$set": {'is_active': False}}
            if is_account_active:
                await accounts_collection.update_one(query, update_query)
                deactivated_accounts.append(account_number)

    return deactivated_accounts


async def get_dates(account_number: str):
    account_exists, account = await get_account_details("account_number", account_number)
    dates = []
    if account_exists:
        async for account in accounts_collection.find():
            account_last_activity = account["created_date"]
            date_format = "%d/%m/%Y"
            account_created = datetime.strptime(account_last_activity, date_format)
            dates.append(account_created)
            bill_date =account_created+ relativedelta(days=30)
            dates.append(bill_date)
            dead_date=bill_date+relativedelta(days=20)
            dates.append(dead_date)

    return dates

