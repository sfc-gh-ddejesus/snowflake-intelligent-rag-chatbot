# 🛠️ Complete Setup Guide

This guide will walk you through setting up the Intelligent Multi-Stage RAG Chatbot with Snowflake Cortex from scratch.

## 📋 **Prerequisites**

### **Snowflake Account Requirements**
- Snowflake account with **Cortex enabled**
- Access to **Cortex Search** and **Cortex LLM functions**
- Warehouse with sufficient compute resources
- Database and schema with appropriate permissions

### **Local Environment**
- **Python 3.11+**
- **Git** for version control
- **Streamlit** for the web interface

## 🎯 **Architecture Overview**

The setup creates two Cortex Search services:
1. **`CS_DOCUMENTS_METADATA`** - Searches document metadata for document discovery
2. **`CS_DOCUMENTS_CHUNKS`** - Searches contextualized chunks for content retrieval

## 📁 **Step 1: Prepare Your Documents**

### **1.1 Upload Documents to Snowflake Stage**

First, create a stage and upload your documents:

```sql
-- Create a stage for your documents
CREATE OR REPLACE STAGE documents
DIRECTORY = (ENABLE = TRUE)
ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- Upload documents using SnowSQL, web interface, or other methods
-- Example using SnowSQL:
-- PUT file://path/to/your/documents/* @documents;
```

### **1.2 Verify Document Upload**

```sql
-- Check uploaded documents
LIST @documents;

-- Verify directory listing
SELECT * FROM DIRECTORY(@documents);
```

## 🔧 **Step 2: Document Processing Pipeline**

### **2.1 Parse Documents with Cortex**

Create the raw parsed documents table:

```sql
CREATE OR REPLACE TABLE DOCUMENTS_RAW_PARSED AS
SELECT 
    RELATIVE_PATH AS FILENAME,
    FILE_URL,
    SIZE,
    LAST_MODIFIED,
    TO_VARCHAR (
        SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
            '@documents',
            relative_path,
             {'mode': 'OCR'}
        )
    ) AS PARSED_CONTENT
FROM 
    DIRECTORY(@documents)
WHERE 
    1 = 1;
```

**What this does:**
- Extracts text from PDFs, Word docs, images using OCR
- Stores the full parsed content for each document
- Maintains file metadata (URL, size, modified date)

### **2.2 Generate Document Metadata**

Create enriched metadata using Claude-4-Sonnet:

```sql
CREATE OR REPLACE TABLE DOCUMENTS_RAW_PARSED_METADATA AS (
    SELECT
        FILENAME,
        FILE_URL,
        PARSED_CONTENT,
        SNOWFLAKE.CORTEX.COMPLETE(
            'claude-4-sonnet', 
            'I am going to provide a document which will be indexed by a retrieval system containing many similar documents. I want you to provide key information associated with this document that can help differentiate this document in the index. Follow these instructions:
        
        1. Do not dwell on low level details. Only provide key high level information that a human might be expected to provide when searching for this doc.
        
        2. Do not use any formatting, just provide keys and values using a colon to separate key and value. Have each key and value be on a new line.
        
        3. Only extract at most the most important keys and values that could be relevant for this document and used in retrieval'   
        || '\n\nDoc starts here:\n' 
        || SUBSTR(PARSED_CONTENT, 0, 4000) 
        || '\nDoc ends here\n\n'
        ) AS CONTENT_METADATA
    FROM
        DOCUMENTS_RAW_PARSED
);
```

**What this does:**
- Uses Claude-4-Sonnet to extract key metadata from each document
- Creates searchable metadata that helps identify and differentiate documents
- Focuses on high-level information relevant for document discovery

### **2.3 Verify Metadata Generation**

```sql
-- Check the generated metadata
SELECT 
    FILENAME,
    CONTENT_METADATA
FROM DOCUMENTS_RAW_PARSED_METADATA
LIMIT 5;

-- Search for specific documents
SELECT * FROM DOCUMENTS_RAW_PARSED_METADATA
WHERE CONTENT_METADATA ILIKE '%agreement%'
   OR CONTENT_METADATA ILIKE '%contract%';
```

## 🔍 **Step 3: Create Cortex Search Services**

### **3.1 Create Metadata Search Service**

```sql
-- CREATE CORTEX SEARCH SERVICE FOR METADATA
CREATE OR REPLACE CORTEX SEARCH SERVICE CS_DOCUMENTS_METADATA
ON CONTENT_METADATA 
ATTRIBUTES FILENAME
WAREHOUSE = DEMO_WH 
TARGET_LAG = '1 minute' 
EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
AS ( 
    SELECT * FROM DOCUMENTS_RAW_PARSED_METADATA 
);
```

**Configuration Details:**
- **Search Column**: `CONTENT_METADATA` - The LLM-generated document summaries
- **Attributes**: `FILENAME` - Used for filtering in the second stage
- **Embedding Model**: `snowflake-arctic-embed-l-v2.0` - High-quality embeddings
- **Target Lag**: `1 minute` - How often the service refreshes

### **3.2 Generate Contextualized Chunks**

Create chunks with prepended context:

```sql
-- STEP 2: GENERATE CHUNKS AND PREPEND CONTEXT TO CHUNK
CREATE OR REPLACE TABLE CHUNKS_CONTEXTUALIZED AS (
    WITH SPLIT_TEXT_CHUNKS AS (
        SELECT
            FILENAME,
            FILE_URL,
            C.VALUE AS CHUNK
        FROM
           DOCUMENTS_RAW_PARSED_METADATA,
           LATERAL FLATTEN( input => SNOWFLAKE.CORTEX.SPLIT_TEXT_RECURSIVE_CHARACTER (
              PARSED_CONTENT,
              'none',
              1800, -- SET CHUNK SIZE
              300   -- SET CHUNK OVERLAP
           )) C
    )
    SELECT
        M.FILENAME,
        M.FILE_URL,
        CONCAT(M.CONTENT_METADATA, '\n\n', C.CHUNK) AS CONTEXTUALIZED_CHUNK
    FROM
        SPLIT_TEXT_CHUNKS C
    JOIN
        DOCUMENTS_RAW_PARSED_METADATA M ON C.FILENAME = M.FILENAME
);
```

**Chunking Strategy:**
- **Chunk Size**: 1800 characters - Optimal for embedding and retrieval
- **Overlap**: 300 characters - Ensures continuity across chunks
- **Contextualization**: Each chunk is prepended with document metadata
- **Recursive Character Splitting**: Preserves sentence and paragraph boundaries

### **3.3 Create Chunks Search Service**

```sql
-- CREATE CORTEX SEARCH SERVICE FOR CHUNKS
CREATE OR REPLACE CORTEX SEARCH SERVICE CS_DOCUMENTS_CHUNKS
ON CONTEXTUALIZED_CHUNK 
ATTRIBUTES FILENAME
WAREHOUSE = DEMO_WH 
TARGET_LAG = '1 minute' 
EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
AS ( 
    SELECT * FROM CHUNKS_CONTEXTUALIZED     
);
```

### **3.4 Verify Search Services**

```sql
-- Check service status
SHOW CORTEX SEARCH SERVICES;

-- Describe the services
DESC CORTEX SEARCH SERVICE CS_DOCUMENTS_METADATA;
DESC CORTEX SEARCH SERVICE CS_DOCUMENTS_CHUNKS;

-- Test the services
SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'CS_DOCUMENTS_METADATA',
    '{"query": "agreement", "limit": 3}'
);

SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'CS_DOCUMENTS_CHUNKS', 
    '{"query": "termination clause", "limit": 3}'
);
```

## 🐍 **Step 4: Local Environment Setup**

### **4.1 Clone the Repository**

```bash
git clone https://github.com/sfc-gh-ddejesus/snowflake-intelligent-rag-chatbot.git
cd snowflake-intelligent-rag-chatbot
```

### **4.2 Install Dependencies**

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### **4.3 Configure Snowflake Connection**

Create a `.streamlit/secrets.toml` file:

```toml
[connections.snowflake]
account = "your-account"
user = "your-username"
password = "your-password"
role = "your-role"
warehouse = "DEMO_WH"
database = "your-database"
schema = "your-schema"
```

**Alternative: Environment Variables**

```bash
export SNOWFLAKE_ACCOUNT="your-account"
export SNOWFLAKE_USER="your-username"
export SNOWFLAKE_PASSWORD="your-password"
export SNOWFLAKE_ROLE="your-role"
export SNOWFLAKE_WAREHOUSE="DEMO_WH"
export SNOWFLAKE_DATABASE="your-database"
export SNOWFLAKE_SCHEMA="your-schema"
```

## 🚀 **Step 5: Run the Application**

### **5.1 Start the Streamlit App**

```bash
streamlit run rag_demo.py
```

### **5.2 Access the Application**

Open your browser to: `http://localhost:8501`

### **5.3 Test the System**

Try these example queries:

**Single Document:**
```
"What are the terms in the CHASE AFFILIATE AGREEMENT?"
```

**Comparison:**
```
"Compare the CHASE AFFILIATE AGREEMENT and Pizza Fusion Holdings, Inc. Franchise Agreement"
```

**Multi-Document:**
```
"What do all the agreements say about termination?"
```

## 🐛 **Step 6: Enable Debug Mode**

1. In the Streamlit sidebar, toggle **"Debug"** to `True`
2. This will show you:
   - Query analysis and intent detection
   - Document search results
   - Synthesis context
   - Fallback triggers

## 🔧 **Troubleshooting**

### **Common Issues**

**1. "No relevant documents found"**
- Check if your stage has documents: `LIST @documents;`
- Verify search services are working: `SHOW CORTEX SEARCH SERVICES;`
- Test metadata quality: `SELECT CONTENT_METADATA FROM DOCUMENTS_RAW_PARSED_METADATA LIMIT 5;`

**2. "Authentication failed"**
- Verify Snowflake credentials in `.streamlit/secrets.toml`
- Check role permissions for Cortex functions
- Ensure warehouse is running

**3. "Cortex Search Service not found"**
- Verify service names match exactly: `CS_DOCUMENTS_METADATA` and `CS_DOCUMENTS_CHUNKS`
- Check service status: `SHOW CORTEX SEARCH SERVICES;`

**4. "Poor search results"**
- Review document metadata quality
- Check if embedding model is appropriate for your content
- Adjust chunk size/overlap parameters

### **Performance Tuning**

**For Large Document Collections:**
- Increase warehouse size for faster processing
- Consider batch processing documents
- Optimize chunk size based on your content

**For Better Search Quality:**
- Improve metadata generation prompts
- Experiment with different embedding models
- Fine-tune chunk size and overlap

## 📊 **Monitoring and Maintenance**

### **Monitor Search Services**
```sql
-- Check service refresh status
SELECT * FROM INFORMATION_SCHEMA.CORTEX_SEARCH_SERVICES 
WHERE SERVICE_NAME IN ('CS_DOCUMENTS_METADATA', 'CS_DOCUMENTS_CHUNKS');

-- Monitor query performance
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVICE_QUERIES 
WHERE SERVICE_NAME IN ('CS_DOCUMENTS_METADATA', 'CS_DOCUMENTS_CHUNKS')
ORDER BY START_TIME DESC;
```

### **Update Documents**
When adding new documents:
1. Upload to stage: `PUT file://new-docs/* @documents;`
2. Refresh tables: Re-run the document processing pipeline
3. Services auto-refresh based on `TARGET_LAG` setting

## ✅ **Verification Checklist**

- [ ] Documents uploaded to Snowflake stage
- [ ] `DOCUMENTS_RAW_PARSED` table created and populated
- [ ] `DOCUMENTS_RAW_PARSED_METADATA` table with quality metadata
- [ ] `CHUNKS_CONTEXTUALIZED` table with proper chunking
- [ ] `CS_DOCUMENTS_METADATA` search service active
- [ ] `CS_DOCUMENTS_CHUNKS` search service active
- [ ] Local environment configured with dependencies
- [ ] Snowflake connection working
- [ ] Streamlit app running successfully
- [ ] Test queries returning expected results

## 🎉 **You're Ready!**

Your Intelligent Multi-Stage RAG Chatbot is now ready to handle sophisticated document queries, comparisons, and multi-document analysis!

For advanced configuration and architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).
