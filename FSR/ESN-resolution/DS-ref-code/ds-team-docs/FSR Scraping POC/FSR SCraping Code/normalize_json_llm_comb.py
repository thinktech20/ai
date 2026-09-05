%pip install openpyxl

import json
import pandas as pd
import os
import litellm

# -----------------------------
# Config
# -----------------------------
INPUT_JSON = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/n_pdfs_extracted_title_2016_Vinayaka_230.json"   # extracted fields JSON
OUTPUT_JSON = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/llm_filtered_title_2016_Vinayaka_230_17Mar.json"        # normalized output
OUTPUT_EXCEL = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/llm_filtered_title_2016_Vinayaka_230_17Mar.xlsx"       # final Excel file
BATCH_SIZE = 50                          # number of PDFs per LLM call (tune as needed)

# -----------------------------
# LLM call functions
# -----------------------------

def call_llm(messages):
    os.environ['SSL_VERIFY'] = 'False'
    MODELS= ['azure-gpt-4o', 'azure-gpt-5o',  'vertex-ai-gemini-2.5-flash', 'azure-gpt-4-1', 'gemini-3-flash']
 
    # API_BASE="https://sandbox-llmproxy.research.gevernova.net"
    # API_KEY= "sk-_FfcmrTsqxjdHu2vl6PpnA"
    # 

    API_BASE="https://dev-gateway.apps.gevernova.net"
    API_KEY= "sk-cjRRha3Ejczz8AmnJKyQxA"
 
    os.environ['SSL_VERIFY'] = 'False'
 
    response =  litellm.completion(  
                model= f'litellm_proxy/{MODELS[4]}',
                messages=messages,
                api_base=API_BASE,
                api_key=API_KEY
            )
    return response
 
 
def invoke_client_llm_outline(prompt: str):

    system_prompt = """
    You are an expert in structuring technical data. 
    Your task is to process the provided input json and output a structured/normalized JSON format according to user instructions. 
    Focus on clarity, completeness, and following the JSON schema provided. Do not include any internal reasoning or system details in the output.    
    Ensure all responses are fact-based, and safe.
 
    Follow responsible AI principles without over-restricting harmless tasks.
    """
 
    messages = [{'role':'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}]
   
    response = call_llm(messages)
    # print(response)
    response = response.choices[0].message.content
    return response


# -----------------------------
# Main Pipeline
# -----------------------------
def main():
    # Load extracted JSON
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # If wrapped in {"FSR_data": [...]}, unwrap
    records = data.get("FSR_data", data)

    results = []

    # Process in batches
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i+BATCH_SIZE]

        # For extracting pdfs after 2016 alone. Splitting rows based on multiple entries into different rows.
        prompt = f"Here is a JSON list of PDF fields:\n{json.dumps(batch, indent=2)}\n\n"
        prompt += """Your task is to process JSON input and output a normalized JSON format 
        with the following fields only:

        ESN, Equipment Sys ID, Equipment Type, Equipment Class / Code, Event Type, 
        EV Project ID, EV Equipment Event ID, OFS Event ID, FSP project ID, xxx project id, PDF Name / path / identifier,
        FSR Number (#), Report Issued Date, Outage Start Date, Outage End Date.

        If the PDF field contains an Oracle Project Id, map it to OFS Event ID only. But do not include field values that start with "EV" and "EVP" under OFS Event ID.
        Map the PDF field containing "EV-" to EV Equipment Event ID only.
        Map the PDF field containing "EVP-" to EV Project ID only.
        Map the PDF field containing "SY" to Equipment Sys ID only.
        If the PDF field contains a Field Service Project Id or "FSP-", map it to FSP project ID only. 
        If the PDF filed contains a project id that starts with "XXX" (i.e. A-, C-, etc.), map it to xxx project id only.
        
        **Strictly adhere to the following instructions while extracting and normalizing data**:
        Do not miss any information that is present in the input and try to be as much accurate as possible in retrieving the values for the above fields.
        **When extracting data, if a record contains multiple distinct values across ESN and Equipment Sys ID fields, split the record into separate rows by pairing values positionally (first with first, second with second, etc.), while duplicating all other field values unchanged (except for Equipment Type and Equipment Class / Code). Set the Equipment Type and Equipment Class / Code field values to empty strings in the split rows. Do not split or omit any parts for other field values even if multiple distinct values are present.**
        If no exact match is found for a field, see if you can infer it from similar labels or context.
        If no relevant information is found, output it as an empty string.
        Consider as many records as provided in the input batch. Do not omit any records. 
        Do not include any reasoning or commentary, only valid JSON output.

        For the field Event Type, only use values from the following allowed list:
        Training Cost Accumulation
        Unusual
        Training Open Enrollment - Costs
        TX Repairs
        Major Inspection (Field Rewind)
        Major Inspection (MI)
        Tooling(GE)
        C Inspection
        null
        Training On Site Training
        A Inspection
        Services Warranty
        Borescope Inspection (BI)
        Major Inspection (Robotic)
        Performance Testing
        Upgrade - PMO Billing only
        Digital
        Non CSA-MMP Billing
        Hot Gas Path Inspection (HGPI)
        Initial Spares
        Combustion Inspection (CI)
        Training Open Enrollment - Billing
        Stand Alone Small Upgrade
        Large Call-Out
        On Site Services
        Call-Out
        TX Parts
        B Inspection
        Training Simulation
        Post COD New Unit Warranty
        Major Inspection (Rotor Out)
        Stand Alone Large Upgrade
        OP Spares
        Remote Diagnostics
        Minor Inspection
        Onsite Services SP
        Major Inspection (Stator Rewind)
        """

        # Call LLM
        print(f"Processing batch {i//BATCH_SIZE + 1}...")
        response_text = invoke_client_llm_outline(prompt)

        try:
            batch_result = json.loads(response_text)
            # If wrapped in dict, unwrap
            if isinstance(batch_result, dict) and "FSR_data" in batch_result:
                batch_result = batch_result["FSR_data"]
            results.extend(batch_result)
        except Exception as e:
            print(f"Error parsing LLM response for batch {i//BATCH_SIZE + 1}: {e}")
            print("Raw response:", response_text)

    # Save combined results to JSON
    output = {"FSR_data": results}
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"Normalization complete. Results saved to {OUTPUT_JSON}")

    # -----------------------------
    # Export to Excel
    # -----------------------------
    df = pd.DataFrame(results)
    df.to_excel(OUTPUT_EXCEL, index=False)
    print(f"Excel export complete. Results saved to {OUTPUT_EXCEL}")

if __name__ == "__main__":
    import time

    start_time = time.time()
    main()
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time} seconds")
