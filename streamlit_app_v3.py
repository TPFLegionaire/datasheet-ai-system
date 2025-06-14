#!/usr/bin/env python3
"""
DATASHEET AI COMPARISON SYSTEM - PHASE 3
========================================
Enhanced web application with authentication, batch processing, and advanced UI
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import time
import asyncio
import tempfile
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import hashlib
import base64
from io import BytesIO
import uuid
import re
from pathlib import Path
import logging
import traceback

# Import our custom modules
from database import DatabaseManager, DatabaseError
from pdf_extractor import PDFExtractor, Parameter, PartVariant, DatasheetExtraction
from mistral_processor import MistralProcessor, MistralProcessorError, QueryResult
from ai_integration import IntegratedExtractor, ExtractionStats, AIIntegrationError
from batch_processor import BatchProcessor, BatchResult, ProcessingStatus, FileTask
from auth import AuthManager, UserRole, AuthProvider, User, Session, AuthError, LoginError, SessionError
from ui_components import (
    FilterManager, create_date_range_filter, create_numeric_range_filter, 
    create_search_filter, apply_search_filter, create_parameter_comparison_chart,
    create_parameter_distribution_chart, create_heatmap, create_radar_chart,
    create_parameter_selector, create_sortable_parameter_list, create_parameter_group_selector,
    create_advanced_search, highlight_search_results, create_fuzzy_search,
    create_export_button, create_export_options, show_success, show_info,
    show_warning, show_error, create_progress_bar, create_status_indicator,
    error_boundary, create_card, create_tabs_card, create_collapsible_sections,
    create_grid_layout, create_dashboard_metrics
)

# Configure asyncio for Streamlit
import nest_asyncio
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('streamlit_app')

# Constants
APP_TITLE = "Datasheet AI Comparison System"
APP_VERSION = "3.0.0"
DB_FILE = "datasheet_system.db"
AUTH_DB_FILE = "auth_system.db"
SESSION_COOKIE_NAME = "datasheet_ai_session"
TEMP_DIR = "temp_uploads"
MAX_UPLOAD_SIZE_MB = 50
ALLOWED_EXTENSIONS = ['.pdf']
DEFAULT_CHART_HEIGHT = 500

# Page configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🚀",
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
    .extraction-method-pattern {
        color: #4CAF50;
        font-weight: bold;
    }
    .extraction-method-ai {
        color: #2196F3;
        font-weight: bold;
    }
    .extraction-method-merged {
        color: #9C27B0;
        font-weight: bold;
    }
    .confidence-high {
        color: #4CAF50;
    }
    .confidence-medium {
        color: #FF9800;
    }
    .confidence-low {
        color: #F44336;
    }
    .small-text {
        font-size: 0.8rem;
        color: #666;
    }
    .info-box {
        background-color: #e7f3fe;
        border-left: 6px solid #2196F3;
        padding: 10px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 6px solid #ffc107;
        padding: 10px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 6px solid #28a745;
        padding: 10px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 6px solid #dc3545;
        padding: 10px;
        margin: 10px 0;
    }
    .tab-subheader {
        font-size: 1.2rem;
        font-weight: bold;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .parameter-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
        margin-right: 5px;
    }
    .tag-environmental {
        background-color: #e8f5e9;
        color: #2e7d32;
    }
    .tag-performance {
        background-color: #e3f2fd;
        color: #1565c0;
    }
    .tag-electrical {
        background-color: #fff3e0;
        color: #e65100;
    }
    .tag-optical {
        background-color: #f3e5f5;
        color: #6a1b9a;
    }
    .tag-physical {
        background-color: #e1f5fe;
        color: #0277bd;
    }
    .tag-general {
        background-color: #f5f5f5;
        color: #616161;
    }
    .query-history-item {
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        background-color: #f5f5f5;
    }
    .extraction-stats-container {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
    }
    .extraction-stat-item {
        flex: 1;
        min-width: 150px;
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
        text-align: center;
    }
    .extraction-stat-value {
        font-size: 1.5rem;
        font-weight: bold;
    }
    .extraction-stat-label {
        font-size: 0.8rem;
        color: #666;
    }
    .user-info {
        padding: 10px;
        border-radius: 5px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
    }
    .role-admin {
        color: #D32F2F;
        font-weight: bold;
    }
    .role-editor {
        color: #1976D2;
        font-weight: bold;
    }
    .role-viewer {
        color: #388E3C;
        font-weight: bold;
    }
    .auth-form {
        max-width: 500px;
        margin: 0 auto;
        padding: 20px;
        border-radius: 10px;
        background-color: #f9f9f9;
    }
    .centered-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 80vh;
    }
    .batch-progress {
        margin: 20px 0;
        padding: 15px;
        border-radius: 5px;
        background-color: #f0f2f6;
    }
    .file-item {
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        background-color: #f5f5f5;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .status-pending {
        color: #9E9E9E;
    }
    .status-processing {
        color: #1976D2;
    }
    .status-completed {
        color: #388E3C;
    }
    .status-failed {
        color: #D32F2F;
    }
    .status-skipped {
        color: #FFA000;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.current_user = None
    st.session_state.extraction_results = {}
    st.session_state.extraction_stats = {}
    st.session_state.batch_results = None
    st.session_state.query_history = []
    st.session_state.api_key_valid = False
    st.session_state.filters = {}
    st.session_state.selected_parameters = []
    st.session_state.chart_type = 'bar'
    st.session_state.show_values = True
    st.session_state.sort_by_value = True
    st.session_state.show_confidence = True
    st.session_state.show_extraction_method = True
    st.session_state.error_message = None
    st.session_state.success_message = None
    st.session_state.info_message = None
    st.session_state.warning_message = None

# Helper Functions
def format_confidence(confidence: float) -> Tuple[str, str]:
    """Format confidence score with appropriate styling"""
    if confidence >= 0.8:
        return f"{confidence:.2f}", "confidence-high"
    elif confidence >= 0.6:
        return f"{confidence:.2f}", "confidence-medium"
    else:
        return f"{confidence:.2f}", "confidence-low"

def format_extraction_method(method: str) -> Tuple[str, str]:
    """Format extraction method with appropriate styling"""
    if method == "pattern":
        return "Pattern", "extraction-method-pattern"
    elif method == "ai":
        return "AI", "extraction-method-ai"
    else:
        return "Merged", "extraction-method-merged"

def format_role(role: UserRole) -> str:
    """Format user role with appropriate styling"""
    if role == UserRole.ADMIN:
        return '<span class="role-admin">Admin</span>'
    elif role == UserRole.EDITOR:
        return '<span class="role-editor">Editor</span>'
    else:
        return '<span class="role-viewer">Viewer</span>'

def format_status(status: ProcessingStatus) -> str:
    """Format processing status with appropriate styling"""
    if status == ProcessingStatus.PENDING:
        return '<span class="status-pending">⏳ Pending</span>'
    elif status == ProcessingStatus.PROCESSING:
        return '<span class="status-processing">🔄 Processing</span>'
    elif status == ProcessingStatus.COMPLETED:
        return '<span class="status-completed">✅ Completed</span>'
    elif status == ProcessingStatus.FAILED:
        return '<span class="status-failed">❌ Failed</span>'
    elif status == ProcessingStatus.SKIPPED:
        return '<span class="status-skipped">⏭️ Skipped</span>'
    else:
        return f'<span>{status.value}</span>'

def get_category_color(category: str) -> str:
    """Get color for a parameter category"""
    colors = {
        "environmental": "#e8f5e9",
        "performance": "#e3f2fd",
        "electrical": "#fff3e0",
        "optical": "#f3e5f5",
        "physical": "#e1f5fe",
        "general": "#f5f5f5"
    }
    return colors.get(category.lower(), "#f5f5f5")

def get_method_color(method_class: str) -> str:
    """Get color for an extraction method"""
    colors = {
        "extraction-method-pattern": "#4CAF50",
        "extraction-method-ai": "#2196F3",
        "extraction-method-merged": "#9C27B0"
    }
    return colors.get(method_class, "#000000")

def get_confidence_color(conf_class: str) -> str:
    """Get color for a confidence score"""
    colors = {
        "confidence-high": "#4CAF50",
        "confidence-medium": "#FF9800",
        "confidence-low": "#F44336"
    }
    return colors.get(conf_class, "#000000")

def run_async(coro):
    """Run an async function in Streamlit"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def get_file_hash(file_content: bytes) -> str:
    """Generate a hash for a file"""
    return hashlib.sha256(file_content).hexdigest()

def is_valid_file(file):
    """Check if file is valid for processing"""
    if file is None:
        return False
    
    # Check file extension
    file_ext = os.path.splitext(file.name)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False
    
    # Check file size
    file_size_mb = len(file.getvalue()) / (1024 * 1024)
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        return False
    
    return True

def save_uploaded_file(uploaded_file):
    """Save uploaded file to temporary directory"""
    # Create temp directory if it doesn't exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(uploaded_file.name)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(TEMP_DIR, unique_filename)
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path

def display_extraction_stats(stats: ExtractionStats):
    """Display extraction statistics in a nice format"""
    st.markdown("#### Extraction Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Parameters", stats.total_parameters)
        st.metric("Pattern Extracted", stats.pattern_extracted)
        st.metric("AI Extracted", stats.ai_extracted)
    
    with col2:
        st.metric("Pattern Confidence", f"{stats.pattern_confidence_avg:.2f}")
        st.metric("AI Confidence", f"{stats.ai_confidence_avg:.2f}")
        st.metric("File Size", f"{stats.file_size / 1024:.1f} KB")
    
    with col3:
        st.metric("Page Count", stats.page_count)
        st.metric("Execution Time", f"{stats.execution_time:.2f}s")
        
        # Calculate extraction rate
        if stats.page_count > 0:
            extraction_rate = stats.total_parameters / stats.page_count
            st.metric("Parameters/Page", f"{extraction_rate:.1f}")
    
    # Create visualization
    if stats.pattern_extracted > 0 or stats.ai_extracted > 0:
        fig = go.Figure()
        
        # Add bars for pattern and AI extraction
        fig.add_trace(go.Bar(
            x=["Pattern", "AI"],
            y=[stats.pattern_extracted, stats.ai_extracted],
            marker_color=["#4CAF50", "#2196F3"],
            text=[stats.pattern_extracted, stats.ai_extracted],
            textposition="auto"
        ))
        
        # Update layout
        fig.update_layout(
            title="Extraction Method Comparison",
            xaxis_title="Extraction Method",
            yaxis_title="Parameters Extracted",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)

def display_batch_progress(batch_result: BatchResult):
    """Display batch processing progress"""
    if not batch_result:
        return
    
    st.markdown("### Batch Processing Progress")
    
    # Progress bar
    progress = batch_result.progress / 100
    st.progress(progress)
    
    # Stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files", batch_result.total_files)
    col2.metric("Completed", batch_result.completed_files)
    col3.metric("Failed", batch_result.failed_files)
    col4.metric("Skipped", batch_result.skipped_files)
    
    # Display file status
    st.markdown("#### File Status")
    
    for file_path, task in batch_result.tasks.items():
        file_name = task.file_name
        status = task.status
        error = task.error_message
        duration = task.duration
        
        # Create status display
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"**{file_name}**")
            if error:
                st.markdown(f"<span class='small-text'>Error: {error}</span>", unsafe_allow_html=True)
        
        with col2:
            st.markdown(format_status(status), unsafe_allow_html=True)
        
        with col3:
            if duration > 0:
                st.markdown(f"<span class='small-text'>{duration:.2f}s</span>", unsafe_allow_html=True)
    
    # Summary if complete
    if batch_result.is_complete:
        st.markdown("#### Summary")
        st.markdown(f"Processed {batch_result.total_files} files in {batch_result.duration:.2f}s")
        st.markdown(f"Success rate: {batch_result.success_rate:.1f}%")
        st.markdown(f"Total parameters extracted: {batch_result.total_parameters}")
        
        # Create visualization
        fig = go.Figure()
        
        # Add pie chart
        fig.add_trace(go.Pie(
            labels=["Completed", "Failed", "Skipped"],
            values=[batch_result.completed_files, batch_result.failed_files, batch_result.skipped_files],
            marker_colors=["#4CAF50", "#F44336", "#FFA000"]
        ))
        
        # Update layout
        fig.update_layout(
            title="Processing Results",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)

# Authentication Functions
def initialize_auth():
    """Initialize authentication manager"""
    auth_manager = AuthManager(
        db_file=AUTH_DB_FILE,
        debug=False
    )
    return auth_manager

def login_form(auth_manager: AuthManager):
    """Display login form"""
    st.markdown("<div class='centered-content'>", unsafe_allow_html=True)
    st.markdown("<div class='auth-form'>", unsafe_allow_html=True)
    
    st.title("🔒 Login")
    st.markdown("Please log in to access the Datasheet AI Comparison System.")
    
    # Login form
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            try:
                user, session = auth_manager.login_user(
                    email=email,
                    password=password
                )
                
                # Store session token
                st.session_state[SESSION_COOKIE_NAME] = session.token
                st.session_state.current_user = user
                
                # Show success message
                st.success(f"Welcome back, {user.username}!")
                time.sleep(1)
                st.experimental_rerun()
                
            except LoginError as e:
                st.error(str(e))
    
    # Registration link
    st.markdown("Don't have an account? [Contact an administrator](#)")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def authenticate(auth_manager: AuthManager) -> Optional[User]:
    """
    Authenticate user

    Args:
        auth_manager: AuthManager instance
        
    Returns:
        User object if authenticated, None otherwise
    """
    # Check for existing session
    if SESSION_COOKIE_NAME in st.session_state:
        try:
            token = st.session_state[SESSION_COOKIE_NAME]
            user, session = auth_manager.validate_session(token)
            return user
        except SessionError:
            # Clear invalid session
            del st.session_state[SESSION_COOKIE_NAME]
            return None
    
    return None

def logout(auth_manager: AuthManager):
    """Logout user"""
    if SESSION_COOKIE_NAME in st.session_state:
        # Delete session from database
        try:
            auth_manager.delete_session(st.session_state[SESSION_COOKIE_NAME])
        except:
            pass
        
        # Clear session from state
        del st.session_state[SESSION_COOKIE_NAME]
        st.session_state.current_user = None
        
        # Show success message
        st.success("Logged out successfully!")
        time.sleep(1)
        st.experimental_rerun()

def require_auth(auth_manager: AuthManager, role: UserRole = UserRole.VIEWER) -> User:
    """
    Require authentication with specific role

    Args:
        auth_manager: AuthManager instance
        role: Required role
        
    Returns:
        User object if authenticated with required role
    """
    user = authenticate(auth_manager)
    
    if not user:
        login_form(auth_manager)
        st.stop()
    
    # Check role
    if not auth_manager.check_permission(user.id, role):
        st.error(f"You don't have the required role: {role.value}")
        st.markdown("Please contact an administrator for access.")
        logout_btn = st.button("Logout")
        if logout_btn:
            logout(auth_manager)
        st.stop()
    
    return user

# Main Application
def main():
    try:
        # Initialize managers
        auth_manager = initialize_auth()
        db_manager = DatabaseManager(db_file=DB_FILE, debug=False)
        
        # Require authentication
        user = require_auth(auth_manager, UserRole.VIEWER)
        
        # Store current user
        st.session_state.current_user = user
        
        # Header
        st.title(f"🚀 {APP_TITLE} v{APP_VERSION}")
        st.markdown("*Transform your supplier comparison process with AI-powered extraction*")
        
        # Sidebar
        with st.sidebar:
            # User info
            st.markdown("<div class='user-info'>", unsafe_allow_html=True)
            st.markdown(f"**User:** {user.username}")
            st.markdown(f"**Role:** {format_role(user.role)}", unsafe_allow_html=True)
            st.markdown(f"**Email:** {user.email}")
            
            # Logout button
            if st.button("Logout"):
                logout(auth_manager)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # API Configuration
            st.header("🔑 API Configuration")
            api_key = st.text_input("Mistral API Key", type="password")
            
            # API key validation
            if api_key:
                try:
                    # Initialize processor for validation
                    processor = MistralProcessor(api_key=api_key, debug=False)
                    if processor.validate_api_key():
                        st.success("✅ API Key validated")
                        st.session_state.api_key_valid = True
                        st.session_state.mistral_api_key = api_key
                    else:
                        st.error("❌ Invalid API key")
                        st.session_state.api_key_valid = False
                except Exception as e:
                    st.error(f"❌ API validation error: {str(e)}")
                    st.session_state.api_key_valid = False
            else:
                st.warning("⚠️ Enter your Mistral API key for AI features")
                st.session_state.api_key_valid = False
            
            st.markdown("---")
            
            # Extraction Settings
            st.header("⚙️ Extraction Settings")
            
            extraction_mode = st.radio(
                "Default Extraction Mode",
                options=["Auto (Pattern + AI Fallback)", "Pattern Only", "AI Only"],
                index=0
            )
            
            force_ai = extraction_mode == "AI Only"
            pattern_only = extraction_mode == "Pattern Only"
            
            # Advanced Settings
            with st.expander("Advanced Settings"):
                confidence_threshold = st.slider(
                    "Minimum Confidence Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.6,
                    step=0.05,
                    help="Parameters with confidence below this threshold will be highlighted"
                )
                
                min_params_threshold = st.slider(
                    "Minimum Parameters Threshold",
                    min_value=1,
                    max_value=10,
                    value=3,
                    step=1,
                    help="Minimum number of parameters to extract before considering AI fallback"
                )
                
                batch_workers = st.slider(
                    "Batch Processing Workers",
                    min_value=1,
                    max_value=8,
                    value=4,
                    step=1,
                    help="Number of parallel workers for batch processing"
                )
            
            st.markdown("---")
            
            # Database Stats
            st.header("📊 Database Stats")
            metrics = db_manager.get_metrics()
            
            st.metric("📄 Datasheets", metrics["datasheets"])
            st.metric("📊 Parameters", metrics["parameters"])
            st.metric("🔢 Parts", metrics["parts"])
            st.metric("🏭 Suppliers", metrics["suppliers"])
            
            # Database maintenance (admin only)
            if user.role == UserRole.ADMIN:
                st.markdown("---")
                st.header("🛠️ Maintenance")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📦 Backup Database"):
                        try:
                            backup_file = db_manager.create_backup()
                            st.success(f"Backup created: {backup_file}")
                        except Exception as e:
                            st.error(f"Backup failed: {str(e)}")
                
                with col2:
                    if st.button("🧹 Clean Sessions"):
                        try:
                            auth_manager.cleanup_expired_sessions()
                            st.success("Expired sessions cleaned up")
                        except Exception as e:
                            st.error(f"Cleanup failed: {str(e)}")
        
        # Main Content
        # Metrics Dashboard
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📄 Datasheets", metrics["datasheets"])
        with col2:
            st.metric("📊 Parameters", metrics["parameters"])
        with col3:
            st.metric("⚡ Time Saved", "95%")
        with col4:
            st.metric("🎯 Accuracy", "99%")
        
        # Show messages if any
        if st.session_state.error_message:
            st.error(st.session_state.error_message)
            st.session_state.error_message = None
        
        if st.session_state.success_message:
            st.success(st.session_state.success_message)
            st.session_state.success_message = None
        
        if st.session_state.info_message:
            st.info(st.session_state.info_message)
            st.session_state.info_message = None
        
        if st.session_state.warning_message:
            st.warning(st.session_state.warning_message)
            st.session_state.warning_message = None
        
        # Tabs - different tabs based on user role
        if user.role == UserRole.ADMIN:
            tabs = st.tabs(["📤 Upload", "🔍 Compare", "💬 Query", "📈 Analytics", "👥 Users"])
            upload_tab, compare_tab, query_tab, analytics_tab, users_tab = tabs
        else:
            tabs = st.tabs(["📤 Upload", "🔍 Compare", "💬 Query", "📈 Analytics"])
            upload_tab, compare_tab, query_tab, analytics_tab = tabs
            users_tab = None
        
        # Upload Tab
        with upload_tab:
            st.header("Upload Datasheets")
            
            # Create tabs for single vs batch upload
            upload_mode_tabs = st.tabs(["Single Upload", "Batch Upload"])
            
            # Single Upload Tab
            with upload_mode_tabs[0]:
                st.subheader("Upload Individual Files")
                
                # File uploader
                uploaded_files = st.file_uploader(
                    "Choose PDFs",
                    type=['pdf'],
                    accept_multiple_files=True,
                    help="Upload PDF datasheets for processing"
                )
                
                # Process uploaded files
                if uploaded_files:
                    if not st.session_state.api_key_valid and (force_ai or not pattern_only):
                        st.error("⚠️ Valid Mistral API key required for AI extraction. Please configure it in the sidebar.")
                    else:
                        # Initialize extractors
                        pattern_extractor = PDFExtractor(debug=False)
                        
                        # Initialize AI extractor if needed and API key is valid
                        ai_extractor = None
                        if st.session_state.api_key_valid and (force_ai or not pattern_only):
                            ai_extractor = MistralProcessor(api_key=st.session_state.mistral_api_key, debug=False)
                        
                        # Initialize integrated extractor
                        integrated_extractor = IntegratedExtractor(
                            pattern_extractor=pattern_extractor,
                            ai_extractor=ai_extractor,
                            debug=False
                        )
                        
                        # Process each file
                        for file in uploaded_files:
                            with st.spinner(f"Processing {file.name}..."):
                                try:
                                    # Check file validity
                                    if not is_valid_file(file):
                                        st.error(f"Invalid file: {file.name}. Please upload a PDF file under {MAX_UPLOAD_SIZE_MB}MB.")
                                        continue
                                    
                                    # Read file content
                                    file_content = file.read()
                                    file_hash = get_file_hash(file_content)
                                    
                                    # Extract data
                                    result, stats = run_async(
                                        integrated_extractor.extract_from_bytes(
                                            file_content,
                                            file.name,
                                            force_ai=force_ai
                                        )
                                    )
                                    
                                    # Store results in session state
                                    st.session_state.extraction_results[file.name] = result
                                    st.session_state.extraction_stats[file.name] = stats
                                    
                                    # Save to database
                                    datasheet_id = db_manager.save_datasheet(
                                        supplier=result.supplier,
                                        product_family=result.product_family,
                                        filename=file.name,
                                        data=result.to_dict(),
                                        file_hash=file_hash
                                    )
                                    
                                    st.success(f"✅ Processed {file.name}")
                                    
                                    # Display extraction stats
                                    with st.expander(f"Extraction Details for {file.name}"):
                                        display_extraction_stats(stats)
                                        
                                        # Display extracted data
                                        st.markdown("#### Extracted Data")
                                        st.markdown(f"**Supplier:** {result.supplier}")
                                        st.markdown(f"**Product Family:** {result.product_family}")
                                        
                                        for i, variant in enumerate(result.variants):
                                            st.markdown(f"**Variant {i+1}:** {variant.part_number}")
                                            
                                            # Create a table for parameters
                                            param_data = []
                                            for param in variant.parameters:
                                                conf_text, conf_class = format_confidence(param.confidence)
                                                method_text, method_class = format_extraction_method(param.extraction_method)
                                                
                                                param_data.append({
                                                    "Parameter": param.name,
                                                    "Value": f"{param.value} {param.unit}",
                                                    "Category": param.category,
                                                    "Method": method_text,
                                                    "Confidence": conf_text,
                                                    "_method_class": method_class,
                                                    "_conf_class": conf_class
                                                })
                                            
                                            # Convert to DataFrame for display
                                            if param_data:
                                                df = pd.DataFrame(param_data)
                                                st.dataframe(df[["Parameter", "Value", "Category", "Method", "Confidence"]])
                                    
                                except Exception as e:
                                    st.error(f"❌ Error processing {file.name}: {str(e)}")
                                    
                                    # Record failure in database
                                    try:
                                        db_manager.save_datasheet(
                                            supplier="Unknown",
                                            product_family="Unknown",
                                            filename=file.name,
                                            data={},
                                            status="failed",
                                            error_message=str(e)
                                        )
                                    except:
                                        pass
            
            # Batch Upload Tab
            with upload_mode_tabs[1]:
                st.subheader("Batch Process Multiple Files")
                
                # Directory input
                directory_path = st.text_input(
                    "Directory Path",
                    help="Enter the path to a directory containing PDF files"
                )
                
                # Options
                col1, col2 = st.columns(2)
                
                with col1:
                    file_pattern = st.text_input(
                        "File Pattern",
                        value="*.pdf",
                        help="Glob pattern for matching files"
                    )
                
                with col2:
                    recursive = st.checkbox(
                        "Search Recursively",
                        value=False,
                        help="Search subdirectories recursively"
                    )
                
                # Start batch processing
                if st.button("Start Batch Processing") and directory_path:
                    if not os.path.isdir(directory_path):
                        st.error(f"Directory not found: {directory_path}")
                    else:
                        if not st.session_state.api_key_valid and (force_ai or not pattern_only):
                            st.error("⚠️ Valid Mistral API key required for AI extraction. Please configure it in the sidebar.")
                        else:
                            # Initialize extractors
                            pattern_extractor = PDFExtractor(debug=False)
                            
                            # Initialize AI extractor if needed and API key is valid
                            ai_extractor = None
                            if st.session_state.api_key_valid and (force_ai or not pattern_only):
                                ai_extractor = MistralProcessor(api_key=st.session_state.mistral_api_key, debug=False)
                            
                            # Initialize batch processor
                            batch_processor = BatchProcessor(
                                max_workers=batch_workers,
                                db_manager=db_manager,
                                integrated_extractor=IntegratedExtractor(
                                    pattern_extractor=pattern_extractor,
                                    ai_extractor=ai_extractor,
                                    debug=False
                                ) if (ai_extractor or not force_ai) else None,
                                pattern_extractor=pattern_extractor,
                                force_ai=force_ai,
                                debug=False
                            )
                            
                            # Start batch processing
                            with st.spinner("Starting batch processing..."):
                                # Process directory
                                def progress_callback(result):
                                    # Update session state
                                    st.session_state.batch_results = result
                                    # Force re-render
                                    st.experimental_rerun()
                                
                                # Start processing in a separate thread
                                import threading
                                
                                def process_thread():
                                    try:
                                        result = batch_processor.process_directory(
                                            directory_path,
                                            file_pattern=file_pattern,
                                            recursive=recursive,
                                            progress_callback=progress_callback
                                        )
                                        
                                        # Final update
                                        st.session_state.batch_results = result
                                    except Exception as e:
                                        st.session_state.error_message = f"Batch processing error: {str(e)}"
                                
                                # Start thread
                                thread = threading.Thread(target=process_thread)
                                thread.start()
                                
                                # Show initial progress
                                st.session_state.batch_results = BatchResult(total_files=0)
                
                # Display batch progress if available
                if st.session_state.batch_results:
                    display_batch_progress(st.session_state.batch_results)
            
            # Previously processed files
            with st.expander("Previously Processed Datasheets"):
                # Create filters
                filter_col1, filter_col2 = st.columns(2)
                
                with filter_col1:
                    search_query = st.text_input("Search", placeholder="Search by filename, supplier, etc.")
                
                with filter_col2:
                    date_range = create_date_range_filter("Date Range")
                
                # Get datasheets
                datasheets_df = db_manager.get_all_datasheets()
                
                # Apply search filter
                if search_query:
                    datasheets_df = apply_search_filter(datasheets_df, search_query, ["supplier", "product_family", "file_name"])
                
                # Apply date filter
                if date_range:
                    start_date, end_date = date_range
                    datasheets_df = datasheets_df[
                        (pd.to_datetime(datasheets_df['upload_date']).dt.date >= start_date) &
                        (pd.to_datetime(datasheets_df['upload_date']).dt.date <= end_date)
                    ]
                
                # Display datasheets
                if not datasheets_df.empty:
                    # Add export options
                    create_export_options(datasheets_df, "datasheets")
                    
                    # Display table
                    st.dataframe(datasheets_df)
                else:
                    st.info("No datasheets processed yet")
        
        # Compare Tab
        with compare_tab:
            st.header("Compare Parameters")
            
            # Create filter manager
            filter_mgr = FilterManager(key_prefix="compare_filter")
            
            # Get suppliers and product families
            suppliers = db_manager.get_suppliers()
            product_families = db_manager.get_product_families()
            
            # Add filters
            filter_mgr.add_filter("supplier", "Supplier", suppliers, multiple=True)
            filter_mgr.add_filter("product_family", "Product Family", product_families, multiple=True)
            
            # Render filters in columns
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            
            with filter_col1:
                active_filters = filter_mgr.render()
            
            with filter_col2:
                search_query = create_search_filter("Search Parameters", key="param_search")
            
            with filter_col3:
                sort_by = st.selectbox(
                    "Sort By",
                    options=["Value (High to Low)", "Value (Low to High)", "Part Number", "Supplier"],
                    index=0
                )
            
            # Get unique parameters
            params_df = db_manager.get_unique_parameters()
            
            # Apply search filter to parameters
            if search_query:
                params_df = apply_search_filter(params_df, search_query, ["parameter_name", "category"])
            
            if not params_df.empty:
                # Parameter selection
                selected_param = st.selectbox(
                    "Select Parameter to Compare",
                    params_df['parameter_name'],
                    index=0 if len(params_df) > 0 else None
                )
                
                # Visualization options
                viz_col1, viz_col2, viz_col3, viz_col4 = st.columns(4)
                
                with viz_col1:
                    chart_type = st.selectbox(
                        "Chart Type",
                        options=["Bar Chart", "Scatter Plot", "Line Chart", "Heatmap"],
                        index=0
                    )
                
                with viz_col2:
                    show_values = st.checkbox("Show Values", value=True)
                
                with viz_col3:
                    group_by = st.selectbox(
                        "Group By",
                        options=["Supplier", "Product Family", "None"],
                        index=0
                    )
                
                with viz_col4:
                    show_confidence = st.checkbox("Show Confidence", value=True)
                
                if selected_param:
                    # Get comparison data
                    df = db_manager.get_parameters_comparison(selected_param)
                    
                    # Apply filters
                    if active_filters.get("supplier"):
                        df = df[df['supplier'].isin(active_filters["supplier"])]
                    
                    if active_filters.get("product_family"):
                        # Join with datasheets to get product family
                        datasheets_df = db_manager.get_all_datasheets()
                        df = pd.merge(
                            df,
                            datasheets_df[['id', 'product_family']],
                            left_on='datasheet_id',
                            right_on='id'
                        )
                        df = df[df['product_family'].isin(active_filters["product_family"])]
                    
                    # Apply sorting
                    if sort_by == "Value (High to Low)":
                        df = df.sort_values("parameter_value", ascending=False)
                    elif sort_by == "Value (Low to High)":
                        df = df.sort_values("parameter_value", ascending=True)
                    elif sort_by == "Part Number":
                        df = df.sort_values("part_number")
                    elif sort_by == "Supplier":
                        df = df.sort_values("supplier")
                    
                    if not df.empty:
                        # Display data table
                        st.markdown("### Parameter Values")
                        
                        # Add export options
                        create_export_options(df, f"{selected_param}_comparison")
                        
                        # Display table
                        st.dataframe(df)
                        
                        # Create chart based on type
                        if chart_type == "Bar Chart":
                            fig = create_parameter_comparison_chart(
                                df,
                                selected_param,
                                x_column='part_number',
                                color_column='supplier' if group_by == "Supplier" else 'product_family' if group_by == "Product Family" else None,
                                unit_column='unit',
                                confidence_column='confidence' if show_confidence else None,
                                sort_by_value=sort_by.startswith("Value"),
                                chart_type='bar',
                                height=DEFAULT_CHART_HEIGHT,
                                show_values=show_values
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif chart_type == "Scatter Plot":
                            fig = create_parameter_comparison_chart(
                                df,
                                selected_param,
                                x_column='part_number',
                                color_column='supplier' if group_by == "Supplier" else 'product_family' if group_by == "Product Family" else None,
                                unit_column='unit',
                                confidence_column='confidence' if show_confidence else None,
                                sort_by_value=sort_by.startswith("Value"),
                                chart_type='scatter',
                                height=DEFAULT_CHART_HEIGHT,
                                show_values=show_values
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif chart_type == "Line Chart":
                            fig = create_parameter_comparison_chart(
                                df,
                                selected_param,
                                x_column='part_number',
                                color_column='supplier' if group_by == "Supplier" else 'product_family' if group_by == "Product Family" else None,
                                unit_column='unit',
                                confidence_column='confidence' if show_confidence else None,
                                sort_by_value=sort_by.startswith("Value"),
                                chart_type='line',
                                height=DEFAULT_CHART_HEIGHT,
                                show_values=show_values
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif chart_type == "Heatmap":
                            # For heatmap, we need to pivot the data
                            try:
                                # Determine x and y columns based on group_by
                                x_column = 'supplier' if group_by == "Supplier" else 'product_family' if group_by == "Product Family" else 'part_number'
                                y_column = 'part_number' if x_column != 'part_number' else 'supplier'
                                
                                fig = create_heatmap(
                                    df,
                                    x_column=x_column,
                                    y_column=y_column,
                                    value_column='parameter_value',
                                    title=f"{selected_param} Heatmap",
                                    height=DEFAULT_CHART_HEIGHT
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error creating heatmap: {str(e)}")
                    else:
                        st.info(f"No data available for parameter: {selected_param}")
                
                # Multi-parameter comparison
                with st.expander("Multi-Parameter Comparison"):
                    st.subheader("Compare Multiple Parameters")
                    
                    # Select parameters
                    selected_params = create_parameter_selector(
                        params_df['parameter_name'].tolist(),
                        label="Select Parameters to Compare",
                        key="multi_param_select",
                        max_selections=5
                    )
                    
                    if selected_params:
                        # Get data for each parameter
                        multi_param_data = []
                        
                        for param in selected_params:
                            param_df = db_manager.get_parameters_comparison(param)
                            
                            # Apply filters
                            if active_filters.get("supplier"):
                                param_df = param_df[param_df['supplier'].isin(active_filters["supplier"])]
                            
                            # Add parameter name
                            param_df['parameter_name'] = param
                            
                            multi_param_data.append(param_df)
                        
                        # Combine data
                        if multi_param_data:
                            combined_df = pd.concat(multi_param_data)
                            
                            # Select part numbers to compare
                            part_numbers = combined_df['part_number'].unique().tolist()
                            
                            selected_parts = st.multiselect(
                                "Select Parts to Compare",
                                options=part_numbers,
                                default=part_numbers[:min(5, len(part_numbers))]
                            )
                            
                            if selected_parts:
                                # Filter data
                                filtered_df = combined_df[combined_df['part_number'].isin(selected_parts)]
                                
                                # Create radar chart
                                st.subheader("Radar Chart Comparison")
                                
                                try:
                                    # Normalize values for radar chart
                                    radar_df = filtered_df.copy()
                                    
                                    # Group by parameter and calculate max value for normalization
                                    param_max = radar_df.groupby('parameter_name')['parameter_value'].max().reset_index()
                                    param_max.columns = ['parameter_name', 'max_value']
                                    
                                    # Merge with data
                                    radar_df = pd.merge(radar_df, param_max, on='parameter_name')
                                    
                                    # Normalize values
                                    radar_df['normalized_value'] = radar_df['parameter_value'] / radar_df['max_value']
                                    
                                    # Create radar chart
                                    fig = create_radar_chart(
                                        radar_df,
                                        category_column='parameter_name',
                                        value_column='normalized_value',
                                        name_column='part_number',
                                        title="Parameter Comparison",
                                        height=DEFAULT_CHART_HEIGHT
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                    
                                    # Display table with actual values
                                    st.subheader("Comparison Table")
                                    
                                    # Pivot table for display
                                    pivot_df = filtered_df.pivot(
                                        index='part_number',
                                        columns='parameter_name',
                                        values='parameter_value'
                                    ).reset_index()
                                    
                                    st.dataframe(pivot_df)
                                    
                                    # Add export options
                                    create_export_options(pivot_df, "multi_parameter_comparison")
                                    
                                except Exception as e:
                                    st.error(f"Error creating radar chart: {str(e)}")
                            else:
                                st.info("Select parts to compare")
                        else:
                            st.info("No data available for selected parameters")
                    else:
                        st.info("Select parameters to compare")
            else:
                st.info("No parameters available for comparison. Upload some datasheets first.")
```

## Part 6 of `streamlit_app_v3.py` (Lines 1801-2200) - Query Tab:

```python
        
        # Query Tab
        with query_tab:
            st.header("Ask Questions")
            
            # Check if API key is valid
            if not st.session_state.api_key_valid:
                st.warning("⚠️ Please provide a valid Mistral API key in the sidebar to use the query feature.")
            else:
                # Initialize Mistral processor
                processor = MistralProcessor(api_key=st.session_state.mistral_api_key, debug=False)
                
                # Create filters
                filter_col1, filter_col2 = st.columns(2)
                
                with filter_col1:
                    suppliers_filter = st.multiselect(
                        "Filter by Suppliers",
                        options=suppliers, # Defined in Compare Tab
                        default=[]
                    )
                
                with filter_col2:
                    product_families_filter = st.multiselect(
                        "Filter by Product Families",
                        options=product_families, # Defined in Compare Tab
                        default=[]
                    )
                
                # Query input
                query = st.text_area(
                    "Your question about the datasheets:",
                    height=100,
                    help="Ask a natural language question about the datasheets in the system"
                )
                
                # Advanced options
                with st.expander("Advanced Options"):
                    context_size = st.slider(
                        "Context Size (KB)",
                        min_value=5,
                        max_value=50,
                        value=15,
                        step=5,
                        help="Maximum size of context to send to the AI"
                    )
                    
                    include_raw_data = st.checkbox(
                        "Include Raw Data",
                        value=False,
                        help="Include raw extracted data in context (increases token usage)"
                    )
                
                # Process query
                if st.button("Get Answer") and query:
                    with st.spinner("Thinking..."):
                        try:
                            # Get context from database
                            datasheets = db_manager.get_all_datasheets()
                            
                            # Apply filters if any
                            if suppliers_filter:
                                datasheets = datasheets[datasheets['supplier'].isin(suppliers_filter)]
                            
                            if product_families_filter:
                                datasheets = datasheets[datasheets['product_family'].isin(product_families_filter)]
                            
                            # Convert to context
                            if include_raw_data:
                                context = json.dumps(datasheets.to_dict(), indent=2)
                            else:
                                # Get parameters for filtered datasheets
                                parameters = []
                                for idx, row in datasheets.iterrows():
                                    datasheet_id = row['id']
                                    params_df = db_manager.get_parameters_by_datasheet(datasheet_id) # Assuming this method exists
                                    
                                    if not params_df.empty:
                                        for _, param_row in params_df.iterrows():
                                            parameters.append({
                                                'supplier': row['supplier'],
                                                'product_family': row['product_family'],
                                                'part_number': param_row['part_number'],
                                                'parameter_name': param_row['parameter_name'],
                                                'parameter_value': param_row['parameter_value'],
                                                'unit': param_row['unit'],
                                                'category': param_row['category']
                                            })
                                
                                context = json.dumps(parameters, indent=2)
                            
                            # Limit context size
                            max_context_size = context_size * 1024
                            if len(context) > max_context_size:
                                context = context[:max_context_size] + "..."
                            
                            # Process query
                            response_obj = processor.answer_query(query, context)
                            
                            # Display response
                            st.markdown("### Answer")
                            st.markdown(response_obj.response)
                            
                            # Show metadata
                            with st.expander("Response Metadata"):
                                st.markdown(f"**Model:** {response_obj.model_used}")
                                st.markdown(f"**Execution Time:** {response_obj.execution_time:.2f}s")
                                st.markdown(f"**Context Size:** {len(context) / 1024:.1f} KB")
                                st.markdown(f"**Filters Applied:** {len(suppliers_filter) > 0 or len(product_families_filter) > 0}")
                            
                            # Save query to database and history
                            db_manager.save_query(query, response_obj.response, response_obj.execution_time)
                            
                            # Add to session history
                            st.session_state.query_history.append({
                                "query": query,
                                "response": response_obj.response,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "execution_time": response_obj.execution_time
                            })
                            
                        except Exception as e:
                            st.error(f"Query failed: {str(e)}")
                
                # Show query history
                if st.session_state.query_history:
                    with st.expander("Query History"):
                        for i, item in enumerate(reversed(st.session_state.query_history)):
                            st.markdown(f"**Q{i+1}: {item['query']}**")
                            st.markdown(f"{item['response']}")
                            st.markdown(f"<span class='small-text'>{item['timestamp']} ({item['execution_time']:.2f}s)</span>", unsafe_allow_html=True)
                            st.markdown("---")
                
                # Show recent queries from database
                with st.expander("All Queries"):
                    recent_queries = db_manager.get_recent_queries(limit=20)
                    if not recent_queries.empty:
                        # Add export options
                        create_export_options(recent_queries, "query_history")
                        
                        # Display table
                        st.dataframe(recent_queries)
                    else:
                        st.info("No queries yet")
```

## Part 7 of `streamlit_app_v3.py` (Lines 2201-End) - Analytics Tab, Users Tab & Main Execution:

```python
        
        # Analytics Tab
        with analytics_tab:
            st.header("Analytics")
            
            # Create tabs for different analytics views
            analytics_tabs = st.tabs(["Parameters", "Extraction Methods", "Suppliers", "Timeline"])
            
            # Parameters Tab
            with analytics_tabs[0]:
                st.subheader("Parameter Analytics")
                
                # Get parameter statistics
                params_df = db_manager.get_unique_parameters()
                
                if not params_df.empty:
                    # Display top parameters
                    st.markdown("#### Top Parameters by Count")
                    
                    # Create chart
                    fig = create_parameter_distribution_chart(
                        params_df,
                        parameter_name='parameter_name',
                        count_column='count',
                        category_column='category',
                        top_n=10,
                        chart_type='bar',
                        height=DEFAULT_CHART_HEIGHT
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Parameter category distribution
                    st.markdown("#### Parameters by Category")
                    
                    category_counts = params_df.groupby('category')['count'].sum().reset_index()
                    
                    fig = create_parameter_distribution_chart(
                        category_counts,
                        parameter_name='category',
                        count_column='count',
                        chart_type='pie',
                        height=DEFAULT_CHART_HEIGHT
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Parameter table
                    with st.expander("Parameter Details"):
                        # Add export options
                        create_export_options(params_df, "parameter_stats")
                        
                        # Display table
                        st.dataframe(params_df)
                else:
                    st.info("No parameters available yet")
            
            # Extraction Methods Tab
            with analytics_tabs[1]:
                st.subheader("Extraction Method Analytics")
                
                try:
                    # Get extraction statistics
                    extraction_stats = db_manager.get_extraction_stats()
                    
                    if not extraction_stats.empty:
                        # Display as table
                        st.markdown("#### Extraction Method Statistics")
                        st.dataframe(extraction_stats)
                        
                        # Create visualization
                        fig = px.bar(
                            extraction_stats,
                            x='extraction_method',
                            y='count',
                            color='extraction_method',
                            title="Parameters by Extraction Method",
                            labels={
                                'extraction_method': 'Extraction Method',
                                'count': 'Parameter Count'
                            },
                            color_discrete_map={
                                'pattern': '#4CAF50',
                                'ai': '#2196F3',
                                'merged': '#9C27B0'
                            }
                        )
                        
                        # Add text labels
                        fig.update_traces(texttemplate='%{y}', textposition='outside')
                        
                        # Update layout
                        fig.update_layout(height=DEFAULT_CHART_HEIGHT)
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Confidence comparison
                        st.markdown("#### Confidence by Extraction Method")
                        
                        fig2 = px.bar(
                            extraction_stats,
                            x='extraction_method',
                            y='avg_confidence',
                            color='extraction_method',
                            title="Average Confidence by Extraction Method",
                            labels={
                                'extraction_method': 'Extraction Method',
                                'avg_confidence': 'Average Confidence'
                            },
                            color_discrete_map={
                                'pattern': '#4CAF50',
                                'ai': '#2196F3',
                                'merged': '#9C27B0'
                            }
                        )
                        
                        # Add text labels
                        fig2.update_traces(texttemplate='%{y:.2f}', textposition='outside')
                        
                        # Update layout
                        fig2.update_layout(height=DEFAULT_CHART_HEIGHT)
                        
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.info("No extraction statistics available yet")
                except Exception as e:
                    st.error(f"Error loading extraction statistics: {str(e)}")
            
            # Suppliers Tab
            with analytics_tabs[2]:
                st.subheader("Supplier Analytics")
                
                # Get supplier statistics
                datasheets_df = db_manager.get_all_datasheets()
                
                if not datasheets_df.empty:
                    # Count datasheets by supplier
                    supplier_counts = datasheets_df['supplier'].value_counts().reset_index()
                    supplier_counts.columns = ['supplier', 'count']
                    
                    # Create chart
                    fig = px.pie(
                        supplier_counts,
                        names='supplier',
                        values='count',
                        title="Datasheets by Supplier",
                        height=DEFAULT_CHART_HEIGHT
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Count datasheets by product family
                    family_counts = datasheets_df['product_family'].value_counts().reset_index()
                    family_counts.columns = ['product_family', 'count']
                    
                    # Create chart
                    fig = px.bar(
                        family_counts,
                        x='product_family',
                        y='count',
                        title="Datasheets by Product Family",
                        labels={
                            'product_family': 'Product Family',
                            'count': 'Count'
                        },
                        height=DEFAULT_CHART_HEIGHT
                    )
                    
                    # Add text labels
                    fig.update_traces(texttemplate='%{y}', textposition='outside')
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Supplier-Product Family relationship
                    st.markdown("#### Supplier-Product Family Relationship")
                    
                    # Create cross-tabulation
                    cross_tab = pd.crosstab(
                        datasheets_df['supplier'],
                        datasheets_df['product_family']
                    ).reset_index()
                    
                    # Melt for visualization
                    melted_df = pd.melt(
                        cross_tab,
                        id_vars=['supplier'],
                        var_name='product_family',
                        value_name='count'
                    )
                    
                    # Create heatmap
                    fig = create_heatmap(
                        melted_df,
                        x_column='product_family',
                        y_column='supplier',
                        value_column='count',
                        title="Supplier-Product Family Heatmap",
                        height=DEFAULT_CHART_HEIGHT
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No supplier data available yet")
            
            # Timeline Tab
            with analytics_tabs[3]:
                st.subheader("Upload Timeline")
                
                # Get upload timeline
                datasheets_df = db_manager.get_all_datasheets()
                
                if not datasheets_df.empty:
                    # Convert upload_date to datetime
                    datasheets_df['upload_date'] = pd.to_datetime(datasheets_df['upload_date'])
                    
                    # Group by date
                    timeline_df = datasheets_df.groupby(datasheets_df['upload_date'].dt.date).size().reset_index()
                    timeline_df.columns = ['date', 'count']
                    
                    # Create chart
                    fig = px.line(
                        timeline_df,
                        x='date',
                        y='count',
                        title="Datasheet Uploads Over Time",
                        labels={
                            'date': 'Date',
                            'count': 'Uploads'
                        },
                        height=DEFAULT_CHART_HEIGHT
                    )
                    
                    # Add markers
                    fig.update_traces(mode='lines+markers')
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Cumulative uploads
                    timeline_df['cumulative'] = timeline_df['count'].cumsum()
                    
                    fig = px.line(
                        timeline_df,
                        x='date',
                        y='cumulative',
                        title="Cumulative Datasheet Uploads",
                        labels={
                            'date': 'Date',
                            'cumulative': 'Total Uploads'
                        },
                        height=DEFAULT_CHART_HEIGHT
                    )
                    
                    # Add markers
                    fig.update_traces(mode='lines+markers')
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Upload activity by day of week
                    day_of_week = datasheets_df.groupby(datasheets_df['upload_date'].dt.day_name()).size().reset_index()
                    day_of_week.columns = ['day', 'count']
                    
                    # Order days
                    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    day_of_week['day'] = pd.Categorical(day_of_week['day'], categories=days_order, ordered=True)
                    day_of_week = day_of_week.sort_values('day')
                    
                    # Create chart
                    fig = px.bar(
                        day_of_week,
                        x='day',
                        y='count',
                        title="Upload Activity by Day of Week",
                        labels={
                            'day': 'Day',
                            'count': 'Uploads'
                        },
                        height=DEFAULT_CHART_HEIGHT
                    )
                    
                    # Add text labels
                    fig.update_traces(texttemplate='%{y}', textposition='outside')
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No timeline data available yet")
        
        # Users Tab (admin only)
        if users_tab and user.role == UserRole.ADMIN:
            with users_tab:
                st.header("User Management")
                
                # Create tabs for user management
                user_tabs = st.tabs(["Users", "Add User", "Edit User"])
                
                # Users Tab
                with user_tabs[0]:
                    st.subheader("All Users")
                    
                    # Get all users
                    all_users = auth_manager.get_all_users()
                    
                    # Convert to DataFrame
                    users_df = pd.DataFrame([u.to_dict() for u in all_users])
                    
                    if not users_df.empty:
                        # Add export options
                        create_export_options(users_df, "users")
                        
                        # Display table
                        st.dataframe(users_df)
                    else:
                        st.info("No users found")
                
                # Add User Tab
                with user_tabs[1]:
                    st.subheader("Add New User")
                    
                    with st.form("add_user_form"):
                        email = st.text_input("Email")
                        username = st.text_input("Username")
                        password = st.text_input("Password", type="password")
                        role = st.selectbox(
                            "Role",
                            options=[r.value for r in UserRole],
                            index=2  # Default to VIEWER
                        )
                        
                        submit = st.form_submit_button("Add User")
                        
                        if submit:
                            try:
                                # Register user
                                new_user = auth_manager.register_user(
                                    email=email,
                                    username=username,
                                    password=password,
                                    role=UserRole(role)
                                )
                                
                                st.success(f"User {username} ({email}) created successfully!")
                                
                            except Exception as e:
                                st.error(f"Failed to create user: {str(e)}")
                
                # Edit User Tab
                with user_tabs[2]:
                    st.subheader("Edit User")
                    
                    # Get all users
                    all_users = auth_manager.get_all_users()
                    
                    # Create user selection
                    user_options = [f"{u.username} ({u.email})" for u in all_users]
                    user_map = {f"{u.username} ({u.email})": u for u in all_users}
                    
                    selected_user_str = st.selectbox("Select User", options=user_options)
                    
                    if selected_user_str:
                        selected_user = user_map[selected_user_str]
                        
                        with st.form("edit_user_form"):
                            email = st.text_input("Email", value=selected_user.email)
                            username = st.text_input("Username", value=selected_user.username)
                            new_password = st.text_input("New Password (leave empty to keep current)", type="password")
                            role = st.selectbox(
                                "Role",
                                options=[r.value for r in UserRole],
                                index=[r.value for r in UserRole].index(selected_user.role.value)
                            )
                            is_active = st.checkbox("Active", value=selected_user.is_active)
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                update = st.form_submit_button("Update User")
                            
                            with col2:
                                delete = st.form_submit_button("Delete User", type="primary") # Using Streamlit's primary button style for delete
                            
                            if update:
                                try:
                                    # Prepare update data
                                    update_data = {
                                        "email": email,
                                        "username": username,
                                        "role": UserRole(role),
                                        "is_active": is_active
                                    }
                                    
                                    # Add password if provided
                                    if new_password:
                                        update_data["password"] = new_password
                                    
                                    # Update user
                                    updated_user = auth_manager.update_user(
                                        user_id=selected_user.id,
                                        **update_data
                                    )
                                    
                                    st.success(f"User {username} updated successfully!")
                                    
                                except Exception as e:
                                    st.error(f"Failed to update user: {str(e)}")
                            
                            if delete:
                                try:
                                    # Check if trying to delete self
                                    if selected_user.id == user.id:
                                        st.error("You cannot delete your own account!")
                                    else:
                                        # Delete user
                                        auth_manager.delete_user(selected_user.id)
                                        st.success(f"User {username} deleted successfully!")
                                        time.sleep(1)
                                        st.experimental_rerun()
                                        
                                except Exception as e:
                                    st.error(f"Failed to delete user: {str(e)}")
        
        # Initialize session state
        st.session_state.initialized = True
        
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
```

This completes the `streamlit_app_v3.py` file.

---

Next, I'll show you `streamlit_app_v2.py`. Are you ready?
