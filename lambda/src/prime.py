# simple lambda function handler to check if the number passing through event is prime or not
# if it is prime then return true else false

def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True


def lambda_handler(event, context):
    action = event['actionGroup']
    api_path = event['apiPath']

    print(action, api_path)
    print(event)

    if api_path == '/prime/':
        number = int(event['parameters'][0]['value'])
        if is_prime(number):
            body = {'isPrime': True}
        else:
            body = {'isPrime': False}

    response_body = {
        'application/json': {
            'body': str(body)
        }
    }

    action_response = {
        'actionGroup': event["actionGroup"],
        'apiPath': event["apiPath"],
        'httpMethod': event["httpMethod"],
        'httpStatusCode': 200,
        'response': response_body
    }

    response = {
        'response': action_response
    }

    return response
