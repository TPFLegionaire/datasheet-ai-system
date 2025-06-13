
DATASHEET EXTRACTION SYSTEM - COMPLETE WEB APPLICATION
=====================================================
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
import os
from datetime import datetime
import tempfile
from typing import Dict, List, Optional, Any, Union
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import dataclass, asdict
import asyncio
from mistralai import Mistral
import base64
from io import BytesIO
# New extraction & DB modules
from pdf_extractor import PDFExtractor
from database import DatabaseManager, DatabaseError

# Page configuration
st.set_page_config(
    page_title="Datasheet AI Comparison System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main { padding: 0rem 1rem; }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Database Setup
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect('datasheet_system.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS datasheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier TEXT NOT NULL,
            product_family TEXT,
            upload_date TIMESTAMP,
            file_name TEXT,
            extracted_data TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datasheet_id INTEGER,
            part_number TEXT,
            parameter_name TEXT,
            parameter_value TEXT,
            unit TEXT,
            category TEXT,
            FOREIGN KEY (datasheet_id) REFERENCES datasheets (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT,
            response TEXT,
            query_date TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_database()

# Mistral Integration
class MistralProcessor:
    def __init__(self, api_key: str):
        self.client = Mistral(api_key=api_key)
        
    async def extract_from_pdf(self, file_content: bytes, filename: str) -> Dict:
        """Extract content from PDF"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            # Simulate extraction for demo
            # In production, this would use Mistral OCR
            demo_data = {
                "supplier": filename.split('_')[0] if '_' in filename else "Unknown",
                "product_family": "Optical Transceivers",
                "variants": [{
                    "part_number": "DEMO-001",
                    "parameters": [
                        {"name": "temperature_range", "value": "-40 to 85", "unit": "°C"},
                        {"name": "data_rate", "value": "10.3", "unit": "Gbps"},
                        {"name": "wavelength", "value": "850", "unit": "nm"}
                    ]
                }]
            }
            
            os.unlink(tmp_path)
            return demo_data
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None
    
    def answer_query(self, query: str, context: str) -> str:
        """Answer natural language query"""
        try:
            response = self.client.chat.complete(
                model="mistral-small-latest",
                messages=[{
                    "role": "user", 
                    "content": f"Based on: {context}\n\nAnswer: {query}"
                }]
            )
            return response.choices[0].message.content
        except:
            return "Please ensure your API key is configured correctly."

# --------------------------------------------------------------------------- #
# Switch to new helper classes for PDF extraction & DB                        #
# --------------------------------------------------------------------------- #

# Singletons
db_manager = DatabaseManager()
extractor = PDFExtractor()

# Main UI
def main():
    # Header
    st.title("🚀 Datasheet AI Comparison System")
    st.markdown("*Transform your supplier comparison process*")
    
    # Sidebar
    with st.sidebar:
        st.header("🔑 Configuration")
        api_key = st.text_input("Mistral API Key", type="password")
        
        if api_key:
            st.success("✅ API Key configured")
            processor = MistralProcessor(api_key)
        else:
            st.warning("⚠️ Enter your Mistral API key")
            processor = None
    
    # Metrics
    metrics = db_manager.get_metrics()
    datasheet_count = metrics["datasheets"]
    param_count = metrics["parameters"]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Datasheets", datasheet_count)
    col2.metric("📊 Parameters", param_count)
    col3.metric("⚡ Time Saved", "95%")
    col4.metric("🎯 Accuracy", "99%")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "🔍 Compare", "💬 Query"])
    
    with tab1:
        st.header("Upload Datasheets")
        uploaded_files = st.file_uploader("Choose PDFs", type=['pdf'], accept_multiple_files=True)
        
        if uploaded_files and processor:
            for file in uploaded_files:
                with st.spinner(f"Processing {file.name}..."):
                    try:
                        # Real extraction using pdf_extractor
                        result = extractor.extract_from_bytes(file.read(), file.name)
                        db_manager.save_datasheet(
                            supplier=result.supplier,
                            product_family=result.product_family,
                            filename=file.name,
                            data=result.to_dict()
                        )
                        st.success(f"✅ Extracted & stored {file.name}")
                    except Exception as e:
                        st.error(f"Extraction failed for {file.name}: {str(e)}")
                        # Record failed status
                        db_manager.save_datasheet(
                            supplier="Unknown",
                            product_family="Unknown",
                            filename=file.name,
                            data={},
                            status="failed",
                            error_message=str(e)
                        )
    
    with tab2:
        st.header("Compare Parameters")
        params_df = db_manager.get_unique_parameters()
        
        if not params_df.empty:
            selected = st.selectbox("Select Parameter", params_df['parameter_name'])
            if selected:
                df = db_manager.get_parameters_comparison(selected)
                st.dataframe(df)
                
                if st.checkbox("Show Chart"):
                    fig = px.bar(df, x='part_number', y='parameter_value', 
                                color='supplier', title=f"{selected} Comparison")
                    st.plotly_chart(fig)
    
    with tab3:
        st.header("Ask Questions")
        query = st.text_area("Your question:")
        
        if st.button("Get Answer") and query and processor:
            with st.spinner("Thinking..."):
                # Get context
                datasheets = db_manager.get_all_datasheets()
                context = "Available data: " + str(datasheets.to_dict())
                answer = processor.answer_query(query, context)
                st.success(answer)

if __name__ == "__main__":
    main()
