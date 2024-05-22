FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}

RUN pip install -r requirements.txt

COPY src/prime.py ${LAMBDA_TASK_ROOT}

RUN chmod 644 ${LAMBDA_TASK_ROOT}/*

CMD [ "prime.handler" ]