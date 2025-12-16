

```python

def move(a: UUID, b: UUID, amount:float, fees:float, currency:str="$"):
    """Move money from account a to b atomically in a C* transaction idempotently"""
    try:
        value = amount + fees

        transfer = Transaction()
        balance = transfer.variable("balance", select(Account).column("balance").where(id=a))
        overdraft = transfer.variable("overdraft", select(Account).column("overdraft").where(id=a))
        credit = transfer.variable("credit", select(OverDraft).column("amount").where(id=a))

        transfer
            .when(balance >= value)\
                .then(update(Account).decr("account_balance", value).where(name=b))\
                .then(update(Account).incr("account_balance", value).where(id=b))\
            .end()
            .when(overdraft and credit >= value)\
                .then(update(OverDraft).decr("amount", value).where(id=a))\
                .then(update(Account).incr("account_balance", 50).where(id=b))\
                .then(insert(Notification).values(text=f"Sent {currency}{amount} to {b}", user=a))\
                .then(insert(Notification).values(text=f"Received {currency}{amount} from {a}", user=b))\
            .end()
        .commit()
    except Exception as e: 
        raise e
    else:
        print("Transaction was successfully executed")

```