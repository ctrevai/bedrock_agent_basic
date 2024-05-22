# simple lambda function handler to check if the number passing through event is prime or not
# if it is prime then return true else false
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(root_path="/prod")
handler = Mangum(app)


# @app.get("/")
# def root():
#     return {"message": "Prime number calculator!"}


@app.get("/prime/{number}")
def prime(number: int):
    if is_prime:
        return {"result": True}
    else:
        return {"result": False}


def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True
