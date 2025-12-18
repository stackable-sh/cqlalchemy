
```python

def move(a: UUID, b: UUID, amount:float, fees:float, currency:str="$"):
    """Move money from account a to b atomically in a C* transaction idempotently"""
    try:
        value = amount + fees

        transfer = Transaction()
        balance = transfer.variable("balance", select(Account).column("balance").where(id=a))
        overdraft = transfer.variable("overdraft", select(Account).column("overdraft").where(id=a))
        credit = transfer.variable("credit", select(OverDraft).column("amount").where(id=a))

        (transfer
            .when(balance >= value)
                .then(update(Account).decr("account_balance", value).where(name=b))
                .then(update(Account).incr("account_balance", value).where(id=b))
            .end()
            .when(overdraft and credit >= value)
                .then(update(OverDraft).decr("amount", value).where(id=a))
                .then(update(Account).incr("account_balance", 50).where(id=b))
                .then(insert(Notification).values(text=f"Sent {currency}{amount} to {b}", user=a))
                .then(insert(Notification).values(text=f"Received {currency}{amount} from {a}", user=b))
            .end()
        .commit())
    except Exception as e: 
        raise e
    else:
        print("Transaction was successfully executed")

```

```python
import cqlalchemy
from cqlalchemy import UUID, String, Email, DateTime
from cqlalchemy import Model

cqlalchemy.configure(keyspace="Example", servers=["127.0.0.1",], port=9042)

# Create a model (with change tracking enabled) for storing user profiles.


class Profile(Model, version=True): 
    """Stores a user profile"""
    name = String(required=True)
    email = Email(required=True, index=True)
    phone = Phone(required=True, index=True)
    created = DateTime(now=True)
    active = Boolean(index=True, default=False)


class Account(Model, version=True):
    """A User Account"""
    credits = Integer()
    password = Password(index=True, required=True)
    profile = Reference(Profile)


class Photo(Model, version=True):
    """Stores a photo for a Profile"""
    id = UUID(primary=True)
    profile = Reference(Profile)
    blob = Blob(required=True)
    url = String(required=True, index=True)
    created = DateTime(now=True)


# Transaction #1: Functional, Fluent API
def reward(account: Account, amount: int):
    """Rewards a user with credits if he has a profile photo and no credits"""
    transfer = Transaction()
    balance = transfer.var("balance", select(Account).column("credits").where(id=account.id))
    photo = transfer.var("photo", select(Photo).where(profile=account.profile))
    transfer\
        .when(photo is not None and balance == 0)\
            .then(update(Account).incr("credits", amount).where(id=account.id))\
            .then(update(Profile).set(active=True).where(id=account.profile))\
        .end()\
    .commit()
    print("Transaction was successfully executed")

# Transaction #2: Contextual, Imperative API
def create(name:str, email:str, password:str, phone:str, photo:bytes):
    """Create a new user account, profile, and photo atomically"""
    atomic = Transaction()
    account, profile, photo = None, None, None
    try:
        with atomic:
            new = atomic.var("new", select(Profile).where(email=email))
            with atomic.when(new is None):
                profile = Profile.create(name=name, email=email, phone=phone)
                account = Account.create(password=password, profile=profile)
                photo = Photo.create(profile=profile, blob=photo)
    except Exception as e:
        raise e
    else:
        print("Transaction was successfully executed")
        Notification.create(user=profile.id, text=f"Welcome {profile.name}")
        return account, profile, photo
    finally:
        atomic.close()

```