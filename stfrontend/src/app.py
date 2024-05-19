import streamlit as st
from sigv4 import SigV4HttpRequester
import json
import boto3
import base64
import io
import time
import random
import string


st.title("Invoice to Pay AI Agent")
st.subheader("Powered by Amazon Bedrock")
st.info("This app is for Invoice to Pay Agent to showcase the AI capability to understand the uploaded pdf invoice and match the PO# with PO record. Policy document can defind the approval process that will be created by AI Agent.")
dorje_logo = "dorje_logo.png"
st.sidebar.image(dorje_logo, width=200, output_format='PNG')
st.sidebar.subheader("Dorje AI demo")
st.sidebar.info("This demo is powered by Dorje AI")

region = 'us-east-1'
modelID = 'amazon.titan-text-express-v1'

agentId = "XSSIC35SEK"
agentAliasId = "ZJ5MQ1V4FG"
dataSourceId = "LUB3AW5OSA"
knowledgeBaseId = "IBOHZTCRT4"
knowledge_base_s3_bucket = "invoice-to-pay-kb"

# session = boto3.Session(region_name=region, profile_name='ctdev')
session = boto3.Session(region_name=region)
bedrock_client = session.client('bedrock')
s3_client = session.client('s3')
agent_client = session.client('bedrock-agent')

approval_query = ''' If invoice amount is less than $100, the invoice is auto approved otherwise the invoice need manual approve.
Check the invoice amount and answer the following question.
what is the invoice amount?
Is the invoice auto approve or manual approve?
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


def delete_previous_invoice():
    print("deleting previous invoice")
    objects_to_delete = s3_client.list_objects_v2(
        Bucket=knowledge_base_s3_bucket)
    if 'Contents' in objects_to_delete:
        for object in objects_to_delete['Contents']:
            print("file to be deleted :" + object['Key'])
            s3_client.delete_object(
                Bucket=knowledge_base_s3_bucket, Key=object['Key'])


def bedrock_agent(query, sessionId):
    if query is not None:

        agent_query = {
            "inputText": query,
            "enableTrace": True,
        }

        print("Invoking Agent with query: " + query)
        agent_url = f"https://bedrock-agent-runtime.{region}.amazonaws.com/agents/{
            agentId}/agentAliases/{agentAliasId}/sessions/{sessionId}/text"
        requester = SigV4HttpRequester()
        response = requester.send_signed_request(
            url=agent_url,
            method='POST',
            service='bedrock',
            headers={
                'content-type': 'application/json',
                'accept': 'application/json'
            },
            region=region,
            body=json.dumps(agent_query)
        )

        if response.status_code == 200:
            response_string = response.text

            split_response = response_string.split(":message-type")

            last_response = split_response[-1]

            try:
                encoded_last_response = last_response.split("\"")[3]

                if encoded_last_response == "citations":
                    # Find the start and end indices of the JSON content
                    start_index = last_response.find('{')
                    end_index = last_response.rfind('}')

                    # Extract the JSON content
                    json_content = last_response[start_index:end_index + 1]

                    try:
                        data = json.loads(json_content)
                        final_response = data['attribution']['citations'][0]['generatedResponsePart']['textResponsePart']['text']
                    except json.decoder.JSONDecodeError as e:
                        print(f"JSON decoding error: {e}")
                    except KeyError as e:
                        print(f"KeyError: {e}")
                else:
                    decoded = base64.b64decode(encoded_last_response)
                    final_response = decoded.decode('utf-8')
            except base64.binascii.Error as e:
                print(f"Base64 decoding error: {e}")
                final_response = last_response  # Or assign a default value

        print("Agent Response: " + final_response)
        return final_response


def bedrock(query):
    if query is not None:

        query_text = {
            "inputText": query
        }

        print("QUERY: " + query)
        bedrock_url = f"https://bedrock-runtime.{
            region}.amazonaws.com/model/{modelID}/invoke"
        requester = SigV4HttpRequester()
        response = requester.send_signed_request(
            url=bedrock_url,
            method='POST',
            service='bedrock',
            headers={
                'content-type': 'application/json',
                'accept': 'application/json'
            },
            region=region,
            body=json.dumps(query_text)
        )

        print("response = " + str(response))
        response_json = json.loads(response.text)
        print("response_json = " + str(response_json))
        print(response_json['results'][0]['outputText'])


def update_knowledge_base(file_content, bucket_name, s3_file_name):
    print("Syncing Invoice to Knowledge Base")

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
                st.write(f"Ingestion Job Status: {job_status}")

            if job_status == "COMPLETE":
                break
            else:
                st.write(
                    f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.write(f"An error occurred: {e}")

        time.sleep(10)  # Poll every 4 seconds (adjust as needed)


def show_pdf(uploaded_file):
    # Display PDF preview
    st.subheader("PDF Preview")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64.b64encode(
        uploaded_file.read()).decode("utf-8")}" width="100%" height="500"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)


def process_uploaded_file(uploaded_file):
    file_name = uploaded_file.name.lower()
    file_extension = file_name.split('.')[-1]

    file_contents = None

    if file_extension == 'pdf':
        show_pdf(uploaded_file)
        file_contents = uploaded_file.getvalue()

    else:
        # Unsupported file type
        st.error("Unsupported file type. Please upload a PDF file.")

    return file_contents


def main():
    if not "valid_inputs_receieved" in st.session_state:
        st.session_state["valid_inputs_receieved"] = False

    # Prompt input
    st.subheader("Invoice Agent - Prompt Input")
    query = st.text_input("Enter your query", value="",
                          placeholder="Ask question about invoice", label_visibility="visible")
    agent_response = None
    if st.session_state.get("previous_query") != query and query != "":
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = session_generator()

        sessionId = st.session_state["session_id"]
        agent_response = bedrock_agent(query, sessionId)
        st.session_state["previous_query"] = query

    if st.button("Submit"):
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = session_generator()
        sessionId = st.session_state["session_id"]
        agent_response = bedrock_agent(query, sessionId)
        st.session_state["previous_query"] = query

    if st.button("Approval Qualification"):
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = session_generator()
        sessionId = st.session_state["session_id"]
        agent_response = bedrock_agent(approval_query, sessionId)
        st.session_state["previous_query"] = query

    if agent_response is not None:
        st.write("Agent's Response: " + agent_response)

    # Invoice upload
    st.subheader("Invoice Agent - Invoice Upload")
    uploaded_file = st.file_uploader("Choose a file", type=["pdf"])
    if uploaded_file is not None:
        # print("uploaded invoice :" + str(uploaded_file))
        # print("current invoice :" + str(st.session_state.get("uploaded_file")))
        if uploaded_file != st.session_state.get("uploaded_file"):
            delete_previous_invoice()
            # print("session state uploaded_file: " + str(st.session_state.get("uploaded_file")))
            st.session_state["uploaded_file"] = uploaded_file
            # print("session state uploaded_file: " + str(st.session_state.get("uploaded_file")))
            print("Uploading new invoice")
            # st.session_state["session_id"] = session_generator()
            file_name = "agent/knowledge-base-assets/invoices/" + \
                "invoice_" + uploaded_file.name
            file_contents = process_uploaded_file(uploaded_file)
            update_knowledge_base(
                file_contents, knowledge_base_s3_bucket, file_name)
            check_ingestion_job_status()
        else:
            show_pdf(uploaded_file)


if __name__ == "__main__":
    main()
