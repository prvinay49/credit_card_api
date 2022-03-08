@app.post("/activate_accounts")
async def activate_accounts(account_number: str):
    try:
        logging.info("activating accounts")
        activated_accounts = await activate_invalid_accounts()
        logging.info("activated accounts")
        return JSONResponse(status_code=200, content={"activated_accounts": activated_accounts})
    except Exception as exception:
        logging.exception(f"Exception occured {exception}")
        traceback.print_exc()
        return JSONResponse(status_code=500,
                                content={"message": f"Error occurred while soft deleting the accounts"})
async def activate_invalid_accounts():

    activated_accounts=list()

    async for account in accounts_collection.find():
            account_number = account["account_number"]
            is_account_active = account["is_active"]
            query = {"account_number": account_number}
            update_query = {"$set": {'is_active': True}}
            if not is_account_active:
                await accounts_collection.update_one(query, update_query)
                activated_accounts.append(account_number)

    return activated_accounts
