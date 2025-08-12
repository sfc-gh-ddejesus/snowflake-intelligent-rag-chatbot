# 📊 CUAD v1 Sample Dataset

This repository includes sample documents from the **Contract Understanding Atticus Dataset (CUAD) v1** to demonstrate the capabilities of the Intelligent Multi-Stage RAG Chatbot with real commercial legal contracts.

## 🎯 **About CUAD**

CUAD is a comprehensive dataset from [The Atticus Project](https://www.atticusprojectai.org/cuad) containing:

- **13,000+ expert labels** in commercial legal contracts
- **510 contracts** manually annotated by experienced lawyers
- **41 categories** of important legal clauses
- **Expert supervision** for corporate transaction analysis (M&A, investments, IPOs)

**Citation**: [CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review](https://arxiv.org/abs/2103.06268) - NeurIPS 2021

## 📁 **Sample Data Structure**

```
CUAD_v1/
├── CUAD_v1_README.txt              # Official CUAD documentation
└── full_contract_pdf/              # Sample PDF contracts
    ├── Part_I/                     # Various contract types
    ├── Part_II/                    # Additional contract categories
    │   ├── Agency Agreements/
    │   ├── Development/
    │   ├── Distributor/
    │   ├── Endorsement/
    │   ├── Hosting/
    │   └── [other categories]/
    └── Part_III/                   # More contract samples
```

## 🔍 **Sample Contract Types**

The included sample contracts cover various commercial agreements:

### **Agency Agreements**
- `AGENCY AGREEMENT1.pdf` - Standard agency relationship contracts
- `AGENCY AGREEMENT2.pdf` - Variations in agency terms

### **Development Agreements**
- `DEVELOPMENT AGREEMENT.pdf` - Software/product development contracts
- `DEVELOPMENT AGREEMENT - First Amendment.pdf` - Contract modifications

### **Distribution Agreements**
- `DISTRIBUTOR AGREEMENT.pdf` - Product distribution contracts
- `AMENDMENT TO THE DISTRIBUTOR AGREEMENT.pdf` - Contract updates

### **Endorsement Agreements**
- `ENDORSEMENT AGREEMENT.pdf` - Celebrity/brand endorsement contracts

### **Hosting Agreements**
- `HOSTING AND MANAGEMENT AGREEMENT.pdf` - Service hosting contracts

## 📋 **41 Legal Clause Categories**

The CUAD dataset identifies these key legal clauses that lawyers examine:

### **Financial & Payment Terms**
- Agreement Date, Effective Date, Expiration Date
- Renewal Term, Notice Period
- Cap on Liability, Liquidated Damages

### **Rights & Obligations**
- License Grant, Exclusive Dealing
- Non-Compete, No-Solicit of Customers/Employees
- IP Ownership Assignment, Joint IP Ownership

### **Compliance & Legal**
- Governing Law, Jurisdiction
- Most Favored Nation, Price Restrictions
- Volume Restriction, ROFR/ROFO/ROFN

### **Business Operations**
- Change of Control, Anti-Assignment
- Revenue/Profit Sharing, Minimum Commitment
- Termination for Convenience/Cause

### **Risk Management**
- Insurance, Indemnification
- Force Majeure, Warranty Duration
- Uncapped Liability, Audit Rights

## 🎯 **Perfect for Testing**

These sample contracts are ideal for demonstrating your RAG chatbot's capabilities:

### **Single Document Queries**
```
"What are the termination clauses in the NETGEAR distributor agreement?"
"What is the governing law for the development agreement?"
"What are the liability limitations in the hosting agreement?"
```

### **Comparison Queries** ⭐
```
"Compare the termination provisions between the agency agreement and distributor agreement"
"What are the differences in IP ownership between the development and endorsement agreements?"
"How do the liability caps vary across the hosting and distribution agreements?"
```

### **Multi-Document Analysis**
```
"What are the common governing law provisions across all agreements?"
"Which contracts have the most restrictive non-compete clauses?"
"How do renewal terms vary across different contract types?"
```

## 🚀 **Using CUAD Data with Your RAG Chatbot**

### **Step 1: Upload to Snowflake Stage**
```sql
-- Upload CUAD PDFs to your Snowflake stage
PUT file://CUAD_v1/full_contract_pdf/Part_I/* @documents;
PUT file://CUAD_v1/full_contract_pdf/Part_II/* @documents;
PUT file://CUAD_v1/full_contract_pdf/Part_III/* @documents;
```

### **Step 2: Process with Setup Notebook**
Follow the instructions in `setup_notebook.ipynb` to:
1. Parse documents with Cortex PARSE_DOCUMENT
2. Generate metadata with Claude-4-Sonnet
3. Create contextualized chunks
4. Build Cortex Search services

### **Step 3: Query with Advanced RAG**
Your chatbot will now intelligently:
- **Analyze query intent** (single-doc vs comparison vs multi-doc)
- **Route to optimal search strategy** (metadata → chunks)
- **Synthesize complex comparisons** across multiple contracts
- **Provide detailed references** with chunk previews

## 📚 **Expert Annotations Available**

The full CUAD dataset includes expert annotations for:
- **Clause identification** by legal category
- **Answer extraction** (Yes/No or specific entities)
- **Context spans** for each legal provision
- **Standardized formatting** across contract variations

## 📖 **Example Legal Questions**

### **Contractual Terms**
- "What is the effective date of this agreement?"
- "Under what conditions can the contract be terminated?"
- "What are the renewal terms?"

### **Legal Compliance**
- "Which state law governs this agreement?"
- "What jurisdiction applies for disputes?"
- "Are there any regulatory compliance requirements?"

### **Business Rights**
- "What intellectual property rights are granted?"
- "Are there any exclusive dealing provisions?"
- "What are the revenue sharing arrangements?"

### **Risk & Liability**
- "What are the liability limitations?"
- "Are there indemnification provisions?"
- "What insurance requirements are specified?"

## 🎓 **Educational Value**

This sample data demonstrates:
- **Real-world complexity** of commercial legal contracts
- **Variety of legal clause types** and formulations
- **Comparative analysis** across different agreement types
- **Advanced RAG capabilities** for legal document analysis

## ⚖️ **License & Attribution**

- **CUAD Dataset**: Licensed under CC BY 4.0
- **Attribution**: The Atticus Project, Inc.
- **Research Paper**: [CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review](https://arxiv.org/abs/2103.06268)
- **Project Website**: https://www.atticusprojectai.org/cuad

## 🔗 **Related Resources**

- **Official CUAD Repository**: https://github.com/TheAtticusProject/cuad
- **Dataset Download**: https://www.atticusprojectai.org/cuad
- **Research Paper**: https://arxiv.org/abs/2103.06268
- **NeurIPS 2021 Presentation**: Available on the Atticus Project website

This sample dataset showcases how your Intelligent Multi-Stage RAG Chatbot excels at sophisticated legal document analysis and comparison tasks! 🚀
