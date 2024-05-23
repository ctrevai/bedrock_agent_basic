import streamlit as st
import boto3
import base64
import io
import time
import random
import string
import json

dorje_logo = "./Dorje logo.svg"

agentId = "XSSIC35SEK"
agentAliasId = "LLGCKF4OII"
dataSourceId = "GB8ECB68O5"
knowledgeBaseId = "65RMT6TTOW"
knowledge_base_s3_bucket = "invoice-to-pay-kb"

# export AWS_PROFILE='your_profile' for local test
session = boto3.Session()
bedrock_client = session.client('bedrock')
s3_client = session.client('s3')
agent_client = session.client('bedrock-agent')
agent_client_runtime = session.client('bedrock-agent-runtime')

approval_query = ''' 

account payable policy are:
If invoice amount is less than $999, auto approve.
If invoice amount is greater than $1000, manual approve.
question:
is this invoice get auto approve or manual approve?

'''


def session_generator():
    # Generate random characters and digits
    digits = ''.join(random.choice(string.digits)
                     for _ in range(4))  # Generating 4 random digits
    chars = ''.join(random.choice(string.ascii_lowercase)
                    for _ in range(3))  # Generating 3 random characters

    # Construct the pattern (1a23b-4c)
    pattern = f"{digits[0]}{chars[0]}{digits[1:3]}{
        chars[1]}-{digits[3]}{chars[2]}"
    print("Session ID: " + str(pattern))

    return pattern


def process_response(response):
    # parse response from bedrock agent runtime for debuging

    print('\nprocess_response', response)

    completion = ''
    return_control_invocation_results = []

    for event in response.get('completion'):

        if 'returnControl' in event:
            return_control = event['returnControl']
            print('\n- returnControl', return_control)
            invocation_id = return_control['invocationId']
            invocation_inputs = return_control['invocationInputs']

            for invocation_input in invocation_inputs:
                function_invocation_input = invocation_input['functionInvocationInput']
                action_group = function_invocation_input['actionGroup']
                function = function_invocation_input['function']
                parameters = function_invocation_input['parameters']
                if action_group == 'retrieve-customer-settings' and function == 'retrieve-customer-settings-from-crm':
                    return_control_invocation_results.append({
                        'functionResult': {
                            'actionGroup': action_group,
                            'function': function,
                            'responseBody': {
                                'TEXT': {
                                    # Simulated API
                                    'body': '{ "customer id": 12345 }'
                                }
                            }
                        }}
                    )

        elif 'chunk' in event:
            chunk = event["chunk"]
            print('\n- chunk', chunk)
            completion = completion + chunk["bytes"].decode()

        elif 'trace' in event:
            trace = event["trace"]
            print('\n- trace', trace)

        else:
            print('\nevent', event)

    if len(completion) > 0:
        print('\ncompletion\n')
        print(completion)


def bedrock(query, sessionId):
    if query is not None:

        response = agent_client_runtime.invoke_agent(
            agentId=agentId,
            agentAliasId=agentAliasId,
            inputText=query,
            enableTrace=True,
            sessionId=sessionId
        )
        # process_response(response)

        agent_response = ""
        for event in response.get("completion"):
            if "chunk" in event:
                chunk = event["chunk"]
                agent_response = agent_response + chunk["bytes"].decode()

        if agent_response is not None:
            return agent_response


def check_ingestion_job_status():

    job_status = ""
    while job_status != "COMPLETE":
        try:
            response = agent_client.list_ingestion_jobs(
                knowledgeBaseId=knowledgeBaseId,
                dataSourceId=dataSourceId,
            )

            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                job_status = response["ingestionJobSummaries"][0]["status"]
                print(f"Ingestion Job Status: {job_status}")
                # st.write(f"Ingestion Job Status: {job_status}")
            else:
                st.write(
                    f"Error: {response['ResponseMetadata']['HTTPStatusCode']}")

            if job_status == "COMPLETE":
                break

        except Exception as e:
            st.write(f"An error occurred: {e}")
        with st.spinner('Wait for Ingestion Job to Complete'):
            time.sleep(10)  # Poll every 4 seconds (adjust as needed)


def show_pdf(uploaded_file):
    # Display PDF preview
    # print("show pdf")
    pdf_file = uploaded_file.read()
    st.subheader("PDF Preview")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64.b64encode(
        pdf_file).decode("utf-8")}" width="100%" height="500"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)


class AnalyseInvoice:

    def update_knowledge_base(self, file_content):
        print("Syncing Invoice to Knowledge Base")
        bucket_name = knowledge_base_s3_bucket
        s3_file_name = "agent/knowledge-base-assets/invoices/" + \
            "invoice_" + st.session_state.uploaded_file.name

        try:
            file_obj = io.BytesIO(file_content)

            s3_client.upload_fileobj(
                file_obj,
                bucket_name,
                s3_file_name,
            )
        except Exception as e:
            st.error(f"Error uploading file to S3: {e}")
            return

        # Ingest the file to the knowledge base
        description = "Ingestion and update knowledge base data source"
        print(description)
        try:
            response = agent_client.start_ingestion_job(
                dataSourceId=dataSourceId,
                knowledgeBaseId=knowledgeBaseId,
                description=description
            )
        except Exception as e:
            st.error(f"Error starting ingestion job: {e}")
        finally:
            file_obj.close()

    def delete_previous_invoice(self):
        print("deleting previous invoice")
        objects_to_delete = s3_client.list_objects_v2(
            Bucket=knowledge_base_s3_bucket, Prefix="agent/knowledge-base-assets/invoices/")
        if 'Contents' in objects_to_delete:
            for object in objects_to_delete['Contents']:
                print("file to be deleted :" + object['Key'])
                s3_client.delete_object(
                    Bucket=knowledge_base_s3_bucket, Key=object['Key'])

    def process_uploaded_file(self):
        file_name = st.session_state.uploaded_file.name.lower()
        file_extension = file_name.split('.')[-1]

        file_contents = None

        if file_extension == 'pdf':
            file_contents = st.session_state.uploaded_file.getvalue()
            return file_contents
        else:
            st.error("Unsupported file type. Please upload a PDF file.")

    def ask_anything(self):

        # Prompt input
        st.subheader("Step 2: Ask anything about your invoice")
        query = st.text_input("Enter your query", value="",
                              placeholder="Ask question about invoice", label_visibility="visible")
        agent_response = None
        if st.session_state.get("previous_query") != query and query != "":
            sessionId = st.session_state["session_id"]
            agent_response = bedrock(query, sessionId)
            st.session_state["previous_query"] = query

        if st.button("Submit"):
            sessionId = st.session_state["session_id"]
            agent_response = bedrock(query, sessionId)
            st.session_state["previous_query"] = query

        if st.button("Check Invoice Qualification"):
            sessionId = st.session_state["session_id"]
            agent_response = bedrock(approval_query, sessionId)
            st.session_state["previous_query"] = query

        if agent_response is not None:
            printable = agent_response.replace("$", "\$")
            st.write(f"Agent's Response:")
            st.write(f"{printable}")

    def upload_invoice(self):
        st.subheader("Step1: Upload Invoice")
        uploaded_file = st.file_uploader(
            "Choose a file", type=["pdf"])
        if uploaded_file is not None:

            if uploaded_file != st.session_state.uploaded_file:
                st.session_state.uploaded_file = uploaded_file
                # st.write("Uploaded file:", uploaded_file.name)

                print("Uploading new invoice")
                st.session_state.session_id = session_generator()
                self.delete_previous_invoice()
                file_contents = self.process_uploaded_file()
                self.update_knowledge_base(file_contents)
                check_ingestion_job_status()
                show_pdf(uploaded_file)
            else:
                show_pdf(uploaded_file)

    def sidebar(self):

        st.sidebar.image(dorje_logo, width=200, output_format='PNG')
        st.sidebar.subheader("Dorje AI demo")
        st.sidebar.info("This demo is powered by Dorje AI")

    def render(self):
        st.set_page_config(page_title="Invoice to Pay AI Agent",
                           page_icon=dorje_logo, layout="wide")

        st.title("Invoice to Pay AI Agent")
        st.subheader("Overview/Introduction")
        st.info('''
            This is a minimum viable product demo of Dorje's AI agent feature. With Dorje AI, users can create custom AI agents to assist with tasks like invoice processing, sales, and workflow optimization. \n
            In this capability demo, we focus on the invoice processing use case, showcasing our agent's ability to interpret uploaded PDF invoices and extract key information in bulk, such as PO record matching, invoice amounts, and supplier details. \n
            Try how our AI agent works through a simple chat prompt. Upload an invoice and ask the agent questions about it. \n
            For the purpose of this demo, the approval qualification for invoices is set at $1000. Invoices below this amount will be auto-processed by the agent.
            ''')

        if "session_id" not in st.session_state:
            st.session_state["session_id"] = session_generator()

        if "previous_query" not in st.session_state:
            st.session_state["previous_query"] = ""

        if "uploaded_file" not in st.session_state:
            st.session_state["uploaded_file"] = None

        if "analyse_complete" not in st.session_state:
            st.session_state["analyse_complete"] = False

        self.sidebar()
        self.upload_invoice()
        self.ask_anything()


if __name__ == "__main__":
    AnalyseInvoice().render()
