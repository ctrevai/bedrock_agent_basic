#simple lambda function handler to check if the number passing through event is prime or not  
#if it is prime then return true else false

def handler(event, context):
    number = int(event['number'])
    return is_prime(number)

def is_prime(n :int ) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True


print(handler({'number': '5'}, None))
print(handler({'number': '4'}, None))