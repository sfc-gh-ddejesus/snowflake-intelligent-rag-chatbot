# 📝 Example Queries

This document provides comprehensive examples of different query types and their expected behavior in the Intelligent Multi-Stage RAG Chatbot.

## 🎯 **Single Document Queries**

These queries focus on extracting information from one specific document or topic.

### **Direct Document Questions**
```
"What are the terms and conditions in the CHASE AFFILIATE AGREEMENT?"
"Tell me about the privacy policy requirements in the user agreement"
"What does the Pizza Fusion franchise agreement say about territory rights?"
"Summarize the key obligations in the partnership contract"
```

### **Specific Information Extraction**
```
"What is the termination clause in the employment contract?"
"How much is the franchise fee mentioned in the agreement?"
"What are the liability limitations in the service contract?"
"When does the confidentiality agreement expire?"
```

### **General Topic Queries**
```
"Tell me about data protection policies"
"What are the standard operating procedures?"
"Explain the employee benefits package"
"What are the safety requirements?"
```

## 🔄 **Comparison Queries** ⭐

These are the chatbot's specialty - sophisticated document comparisons that trigger the parallel search and synthesis workflow.

### **Direct Document Comparisons**
```
"Compare the CHASE AFFILIATE AGREEMENT and Pizza Fusion Holdings, Inc. Franchise Agreement"
"What are the differences between Contract A and Contract B?"
"How do the IBM and Microsoft partnership agreements differ?"
"Compare the termination clauses in all employment contracts"
```

### **Feature-Specific Comparisons**
```
"Compare the liability terms between the supplier agreements"
"What are the differences in payment terms across all contracts?"
"How do the confidentiality requirements vary between documents?"
"Compare the intellectual property clauses in the licensing agreements"
```

### **Multi-Aspect Comparisons**
```
"Compare the rights and obligations in both franchise agreements"
"How do the pricing models differ between the service contracts?"
"What are the key differences in dispute resolution across agreements?"
"Compare the performance metrics in all vendor contracts"
```

## 🌐 **Multi-Document Queries**

These queries require synthesizing information from multiple documents without direct comparison.

### **Comprehensive Analysis**
```
"What do all the franchise agreements say about termination?"
"How is intellectual property handled across all contracts?"
"What are the common liability limitations in our agreements?"
"Summarize the payment terms across all vendor contracts"
```

### **Pattern Identification**
```
"What are the most common clauses across all agreements?"
"Which contracts have the strictest confidentiality requirements?"
"What are the typical penalty structures in our contracts?"
"How consistent are our force majeure clauses?"
```

### **Compliance and Risk Analysis**
```
"Which agreements might conflict with our new data protection policy?"
"What are the potential compliance risks across all contracts?"
"Which contracts have the highest liability exposure?"
"What are the renewal requirements across all agreements?"
```

## 🧠 **Chat History Context Queries**

These demonstrate how the system uses conversation context to enhance responses.

### **Follow-up Questions**
```
User: "Tell me about the CHASE AFFILIATE AGREEMENT"
Bot: [Provides overview]
User: "What about the termination clauses?" 
# System combines: CHASE AFFILIATE AGREEMENT + termination clauses
```

### **Contextual Comparisons**
```
User: "Explain the Pizza Fusion franchise agreement"
Bot: [Provides details]
User: "How does it compare to the CHASE agreement?"
# System understands to compare Pizza Fusion vs CHASE
```

### **Progressive Analysis**
```
User: "What are the key terms in our vendor contracts?"
Bot: [Summarizes vendor terms]
User: "Which ones have the best payment terms?"
# System filters previous results for payment terms
```

## 🎨 **Advanced Query Patterns**

### **Conditional Queries**
```
"If we terminate the CHASE agreement early, what are the penalties?"
"What happens if the Pizza Fusion franchise fails to meet sales targets?"
"Under what conditions can we modify the partnership agreement?"
```

### **Timeline-Based Queries**
```
"What agreements are up for renewal this year?"
"Which contracts have expired or will expire soon?"
"What are the notice periods for termination across all agreements?"
```

### **Financial Analysis**
```
"What are the total financial obligations across all contracts?"
"Compare the cost structures in the franchise agreements"
"Which agreements have the highest recurring fees?"
```

## 🎯 **Query Types Recognition**

Here's how the system categorizes different query patterns:

### **Single Document** → Standard two-stage search
- Contains one specific document name
- General topic without comparisons
- Direct information extraction

### **Comparison** → Parallel search + synthesis
- Contains "compare", "difference", "versus"
- Mentions multiple specific documents
- Asks about variations between items

### **Multi-Document** → Sequential search + synthesis
- Uses "all", "across", "common", "typical"
- Asks about patterns or summaries
- Requires information from multiple sources

### **General** → Fallback to standard search
- Broad questions without specific documents
- Requests for general information
- Questions that don't fit other categories

## 💡 **Tips for Effective Queries**

### **For Best Results:**
1. **Be Specific**: Use exact document names when known
2. **Use Keywords**: Include relevant terms like "termination", "liability", "fees"
3. **Ask Comparative Questions**: The system excels at comparisons
4. **Follow Up**: Use conversation context for deeper analysis

### **Document Name Formats:**
- Use full names: "CHASE AFFILIATE AGREEMENT" 
- Include key identifiers: "Pizza Fusion Holdings, Inc. Franchise Agreement"
- Be consistent with capitalization as it appears in documents

### **Comparison Query Structure:**
```
"Compare [Document A] and [Document B]"
"What are the differences between [Document A] and [Document B]?"
"How do [Document A] and [Document B] differ in terms of [specific aspect]?"
```

## 🐛 **Debug Mode Examples**

Enable debug mode to see how queries are processed:

### **Query Analysis Example:**
```
Input: "Compare the CHASE and Pizza Fusion agreements"

Debug Output:
- Query Type: comparison
- Documents: ["CHASE AFFILIATE AGREEMENT", "Pizza Fusion Holdings, Inc. Franchise Agreement"]  
- Search Queries: ["CHASE AFFILIATE AGREEMENT", "Pizza Fusion Holdings, Inc. Franchise Agreement"]
- Workflow: Parallel RAG
```

### **Search Results Example:**
```
Metadata Search: Found 3 relevant documents for CHASE
Chunks Search: Retrieved 5 chunks from CHASE agreement
Synthesis: Comparing CHASE vs Pizza Fusion terms
```

This comprehensive set of examples demonstrates the full capabilities of your Intelligent Multi-Stage RAG Chatbot!
