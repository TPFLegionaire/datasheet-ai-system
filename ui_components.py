#!/usr/bin/env python3
"""
UI Components Module for Datasheet AI Comparison System

This module provides advanced UI components for the Streamlit application:
1. Multi-level filtering for datasheets
2. Visualization components for comparison views
3. Interactive parameter selection and sorting
4. Advanced search functionality
5. Data export options
6. Enhanced error handling and feedback components
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
import base64
import io
import json
import time
import re
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ui_components')

# -----------------------------------------------------------------------------
# Multi-level Filtering Components
# -----------------------------------------------------------------------------

class FilterManager:
    """
    Manages multi-level filtering for datasheet parameters
    
    This class provides a UI for filtering datasheets by supplier,
    product family, parameters, and other attributes.
    """
    
    def __init__(self, key_prefix: str = "filter"):
        """
        Initialize the filter manager
        
        Args:
            key_prefix: Prefix for Streamlit widget keys
        """
        self.key_prefix = key_prefix
        self.filters = {}
        self.active_filters = {}
    
    def add_filter(self, name: str, label: str, options: List[Any], 
                  default: Optional[Any] = None, 
                  multiple: bool = False,
                  dependent_on: Optional[str] = None):
        """
        Add a filter to the manager
        
        Args:
            name: Filter name (used as key)
            label: Display label
            options: List of filter options
            default: Default selected value
            multiple: Allow multiple selections
            dependent_on: Name of filter this depends on
        """
        self.filters[name] = {
            "label": label,
            "options": options,
            "default": default,
            "multiple": multiple,
            "dependent_on": dependent_on
        }
    
    def render(self, container=None):
        """
        Render all filters in the UI
        
        Args:
            container: Streamlit container to render in (optional)
        
        Returns:
            Dictionary of active filters
        """
        target = container if container else st
        
        # Process filters in dependency order
        processed = set()
        self.active_filters = {}
        
        # First process filters with no dependencies
        for name, config in self.filters.items():
            if not config["dependent_on"]:
                self._render_filter(name, config, target)
                processed.add(name)
        
        # Then process filters with dependencies
        remaining = set(self.filters.keys()) - processed
        while remaining:
            for name in list(remaining):
                config = self.filters[name]
                if config["dependent_on"] in processed:
                    self._render_filter(name, config, target)
                    processed.add(name)
                    remaining.remove(name)
            
            # Break if no progress is made (circular dependencies)
            if not processed.intersection(remaining):
                for name in remaining:
                    logger.warning(f"Filter {name} has unresolved dependency: {self.filters[name]['dependent_on']}")
                break
        
        return self.active_filters
    
    def _render_filter(self, name: str, config: Dict[str, Any], container):
        """
        Render a single filter
        
        Args:
            name: Filter name
            config: Filter configuration
            container: Streamlit container
        """
        label = config["label"]
        options = config["options"]
        default = config["default"]
        multiple = config["multiple"]
        dependent_on = config["dependent_on"]
        
        # Handle dependency
        if dependent_on and dependent_on in self.active_filters:
            parent_value = self.active_filters[dependent_on]
            
            # If options is a function, call it with parent value
            if callable(options):
                options = options(parent_value)
        
        # Skip if no options
        if not options or len(options) == 0:
            return
        
        # Ensure default is in options
        if default is not None and default not in options:
            default = None
        
        # Create widget key
        key = f"{self.key_prefix}_{name}_{uuid.uuid4()}"
        
        # Render appropriate widget
        if multiple:
            selected = container.multiselect(
                label=label,
                options=options,
                default=default if isinstance(default, list) else [],
                key=key
            )
        else:
            if default is None and options:
                default = options[0]
            
            selected = container.selectbox(
                label=label,
                options=options,
                index=options.index(default) if default in options else 0,
                key=key
            )
        
        # Store selected value
        self.active_filters[name] = selected
    
    def apply_filters(self, df: pd.DataFrame, mapping: Dict[str, str] = None) -> pd.DataFrame:
        """
        Apply active filters to a DataFrame
        
        Args:
            df: DataFrame to filter
            mapping: Mapping from filter names to DataFrame column names
        
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        filtered_df = df.copy()
        
        for name, value in self.active_filters.items():
            if value is None or (isinstance(value, list) and len(value) == 0):
                continue
            
            # Get column name from mapping or use filter name
            column = name
            if mapping and name in mapping:
                column = mapping[name]
            
            # Skip if column doesn't exist
            if column not in filtered_df.columns:
                continue
            
            # Apply filter
            if isinstance(value, list):
                filtered_df = filtered_df[filtered_df[column].isin(value)]
            else:
                filtered_df = filtered_df[filtered_df[column] == value]
        
        return filtered_df

def create_date_range_filter(label: str = "Date Range", key: str = "date_range"):
    """
    Create a date range filter
    
    Args:
        label: Filter label
        key: Streamlit widget key
    
    Returns:
        Tuple of (start_date, end_date)
    """
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(f"{label} (Start)", key=f"{key}_start")
    
    with col2:
        end_date = st.date_input(f"{label} (End)", key=f"{key}_end")
    
    return start_date, end_date

def create_numeric_range_filter(label: str, min_val: float, max_val: float, 
                               step: float = 1.0, default: Tuple[float, float] = None,
                               key: str = "numeric_range"):
    """
    Create a numeric range filter
    
    Args:
        label: Filter label
        min_val: Minimum value
        max_val: Maximum value
        step: Step size
        default: Default range as (min, max)
        key: Streamlit widget key
    
    Returns:
        Tuple of (min_value, max_value)
    """
    if default is None:
        default = (min_val, max_val)
    
    return st.slider(
        label=label,
        min_value=min_val,
        max_value=max_val,
        value=default,
        step=step,
        key=key
    )

def create_search_filter(label: str = "Search", key: str = "search", 
                        placeholder: str = "Search...", 
                        help_text: str = "Enter search terms"):
    """
    Create a search text input filter
    
    Args:
        label: Filter label
        key: Streamlit widget key
        placeholder: Placeholder text
        help_text: Help text
    
    Returns:
        Search query string
    """
    return st.text_input(
        label=label,
        key=key,
        placeholder=placeholder,
        help=help_text
    )

def apply_search_filter(df: pd.DataFrame, search_query: str, 
                       columns: List[str] = None) -> pd.DataFrame:
    """
    Apply search filter to DataFrame
    
    Args:
        df: DataFrame to filter
        search_query: Search query string
        columns: Columns to search (if None, search all string columns)
    
    Returns:
        Filtered DataFrame
    """
    if not search_query or df.empty:
        return df
    
    # Determine columns to search
    if columns is None:
        columns = df.select_dtypes(include=['object']).columns.tolist()
    
    # Create search mask
    mask = pd.Series(False, index=df.index)
    
    for col in columns:
        if col in df.columns:
            # Convert column to string and search
            mask = mask | df[col].astype(str).str.contains(search_query, case=False, na=False)
    
    return df[mask]

# -----------------------------------------------------------------------------
# Visualization Components
# -----------------------------------------------------------------------------

def create_parameter_comparison_chart(df: pd.DataFrame, 
                                     parameter_name: str,
                                     x_column: str = 'part_number',
                                     color_column: Optional[str] = 'supplier',
                                     unit_column: Optional[str] = 'unit',
                                     confidence_column: Optional[str] = 'confidence',
                                     sort_by_value: bool = True,
                                     chart_type: str = 'bar',
                                     height: int = 500,
                                     show_values: bool = True) -> go.Figure:
    """
    Create a parameter comparison chart
    
    Args:
        df: DataFrame with parameter data
        parameter_name: Name of parameter being compared
        x_column: Column to use for x-axis
        color_column: Column to use for color grouping
        unit_column: Column containing units
        confidence_column: Column containing confidence scores
        sort_by_value: Whether to sort by parameter value
        chart_type: Chart type ('bar', 'scatter', 'line')
        height: Chart height
        show_values: Whether to show values on bars
    
    Returns:
        Plotly figure
    """
    if df.empty:
        # Create empty figure with message
        fig = go.Figure()
        fig.update_layout(
            title=f"No data available for {parameter_name}",
            height=height,
            annotations=[{
                'text': "No data available",
                'xref': "paper",
                'yref': "paper",
                'x': 0.5,
                'y': 0.5,
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        return fig
    
    # Make a copy to avoid modifying original
    plot_df = df.copy()
    
    # Get unit if available
    unit = ""
    if unit_column in plot_df.columns and not plot_df[unit_column].empty:
        unit = plot_df[unit_column].iloc[0]
    
    # Try to convert parameter_value to numeric
    if 'parameter_value' in plot_df.columns:
        try:
            plot_df['parameter_value'] = pd.to_numeric(plot_df['parameter_value'], errors='coerce')
        except:
            pass
    
    # Sort by value if requested
    if sort_by_value and 'parameter_value' in plot_df.columns:
        plot_df = plot_df.sort_values('parameter_value', ascending=False)
    
    # Create figure based on chart type
    if chart_type == 'bar':
        fig = px.bar(
            plot_df,
            x=x_column,
            y='parameter_value',
            color=color_column if color_column in plot_df.columns else None,
            title=f"{parameter_name} Comparison",
            labels={
                'parameter_value': f"Value ({unit})" if unit else "Value",
                x_column: x_column.replace('_', ' ').title()
            },
            height=height
        )
        
        # Add confidence as marker opacity if available
        if confidence_column in plot_df.columns:
            for i, trace in enumerate(fig.data):
                trace.marker.opacity = plot_df[confidence_column].values
        
        # Show values on bars
        if show_values:
            fig.update_traces(
                texttemplate='%{y}',
                textposition='outside'
            )
        
    elif chart_type == 'scatter':
        fig = px.scatter(
            plot_df,
            x=x_column,
            y='parameter_value',
            color=color_column if color_column in plot_df.columns else None,
            title=f"{parameter_name} Comparison",
            labels={
                'parameter_value': f"Value ({unit})" if unit else "Value",
                x_column: x_column.replace('_', ' ').title()
            },
            height=height,
            size=confidence_column if confidence_column in plot_df.columns else None,
            hover_data=['parameter_value']
        )
        
    elif chart_type == 'line':
        fig = px.line(
            plot_df,
            x=x_column,
            y='parameter_value',
            color=color_column if color_column in plot_df.columns else None,
            title=f"{parameter_name} Comparison",
            labels={
                'parameter_value': f"Value ({unit})" if unit else "Value",
                x_column: x_column.replace('_', ' ').title()
            },
            height=height,
            markers=True
        )
    
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    
    # Update layout
    fig.update_layout(
        xaxis={'categoryorder': 'total descending'},
        margin=dict(t=50, b=50, l=50, r=50)
    )
    
    return fig

def create_parameter_distribution_chart(df: pd.DataFrame, 
                                       parameter_name: str = 'parameter_name',
                                       count_column: str = 'count',
                                       category_column: Optional[str] = 'category',
                                       top_n: int = 10,
                                       chart_type: str = 'bar',
                                       height: int = 500) -> go.Figure:
    """
    Create a parameter distribution chart
    
    Args:
        df: DataFrame with parameter counts
        parameter_name: Column containing parameter names
        count_column: Column containing counts
        category_column: Column for grouping by category
        top_n: Number of top parameters to show
        chart_type: Chart type ('bar', 'pie')
        height: Chart height
    
    Returns:
        Plotly figure
    """
    if df.empty:
        # Create empty figure with message
        fig = go.Figure()
        fig.update_layout(
            title="Parameter Distribution",
            height=height,
            annotations=[{
                'text': "No data available",
                'xref': "paper",
                'yref': "paper",
                'x': 0.5,
                'y': 0.5,
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        return fig
    
    # Make a copy to avoid modifying original
    plot_df = df.copy()
    
    # Sort and limit to top N
    plot_df = plot_df.sort_values(count_column, ascending=False).head(top_n)
    
    # Create figure based on chart type
    if chart_type == 'bar':
        fig = px.bar(
            plot_df,
            x=parameter_name,
            y=count_column,
            color=category_column if category_column in plot_df.columns else None,
            title="Parameter Distribution",
            labels={
                parameter_name: "Parameter",
                count_column: "Count"
            },
            height=height
        )
        
        # Show values on bars
        fig.update_traces(
            texttemplate='%{y}',
            textposition='outside'
        )
        
    elif chart_type == 'pie':
        fig = px.pie(
            plot_df,
            names=parameter_name,
            values=count_column,
            title="Parameter Distribution",
            height=height
        )
        
        # Show percentages
        fig.update_traces(
            textinfo='percent+label'
        )
        
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    
    # Update layout
    fig.update_layout(
        margin=dict(t=50, b=50, l=50, r=50)
    )
    
    return fig

def create_heatmap(df: pd.DataFrame,
                  x_column: str,
                  y_column: str,
                  value_column: str,
                  title: str = "Heatmap",
                  colorscale: str = "Viridis",
                  height: int = 600) -> go.Figure:
    """
    Create a heatmap visualization
    
    Args:
        df: DataFrame with data
        x_column: Column for x-axis
        y_column: Column for y-axis
        value_column: Column for values
        title: Chart title
        colorscale: Colorscale name
        height: Chart height
    
    Returns:
        Plotly figure
    """
    if df.empty:
        # Create empty figure with message
        fig = go.Figure()
        fig.update_layout(
            title=title,
            height=height,
            annotations=[{
                'text': "No data available",
                'xref': "paper",
                'yref': "paper",
                'x': 0.5,
                'y': 0.5,
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        return fig
    
    # Pivot data for heatmap
    try:
        pivot_df = df.pivot(index=y_column, columns=x_column, values=value_column)
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=pivot_df.values,
            x=pivot_df.columns,
            y=pivot_df.index,
            colorscale=colorscale,
            hoverongaps=False
        ))
        
        # Update layout
        fig.update_layout(
            title=title,
            height=height,
            xaxis_title=x_column.replace('_', ' ').title(),
            yaxis_title=y_column.replace('_', ' ').title()
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating heatmap: {str(e)}")
        
        # Create empty figure with error message
        fig = go.Figure()
        fig.update_layout(
            title=title,
            height=height,
            annotations=[{
                'text': f"Error creating heatmap: {str(e)}",
                'xref': "paper",
                'yref': "paper",
                'x': 0.5,
                'y': 0.5,
                'showarrow': False,
                'font': {'size': 16}
            }]
        )
        return fig

def create_radar_chart(df: pd.DataFrame,
                      category_column: str,
                      value_column: str,
                      name_column: Optional[str] = None,
                      title: str = "Radar Chart",
                      height: int = 500) -> go.Figure:
    """
    Create a radar chart for comparing multiple items across categories
    
    Args:
        df: DataFrame with data
        category_column: Column for radar chart categories
        value_column: Column for values
        name_column: Column for item names
        title: Chart title
        height: Chart height
    
    Returns:
        Plotly figure
    """
    if df.empty:
        # Create empty figure with message
        fig = go.Figure()
        fig.update_layout(
            title=title,
            height=height,
            annotations=[{
                'text': "No data available",
                'xref': "paper",
                'yref': "paper",
                'x': 0.5,
                'y': 0.5,
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        return fig
    
    # Create radar chart
    fig = go.Figure()
    
    # Group by name if provided
    if name_column:
        for name, group in df.groupby(name_column):
            fig.add_trace(go.Scatterpolar(
                r=group[value_column],
                theta=group[category_column],
                fill='toself',
                name=name
            ))
    else:
        fig.add_trace(go.Scatterpolar(
            r=df[value_column],
            theta=df[category_column],
            fill='toself'
        ))
    
    # Update layout
    fig.update_layout(
        title=title,
        height=height,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, df[value_column].max() * 1.1]
            )
        )
    )
    
    return fig

# -----------------------------------------------------------------------------
# Interactive Parameter Selection Components
# -----------------------------------------------------------------------------

def create_parameter_selector(available_parameters: List[str],
                             label: str = "Select Parameters",
                             key: str = "param_select",
                             default: List[str] = None,
                             max_selections: Optional[int] = None) -> List[str]:
    """
    Create a multi-select parameter selector
    
    Args:
        available_parameters: List of available parameters
        label: Selector label
        key: Streamlit widget key
        default: Default selected parameters
        max_selections: Maximum number of parameters that can be selected
    
    Returns:
        List of selected parameters
    """
    if not available_parameters:
        st.warning("No parameters available for selection")
        return []
    
    # Set default if not provided
    if default is None:
        default = []
    else:
        # Ensure default only includes available parameters
        default = [p for p in default if p in available_parameters]
    
    # Create help text
    help_text = "Select parameters to include"
    if max_selections:
        help_text += f" (max {max_selections})"
    
    # Create selector
    selected = st.multiselect(
        label=label,
        options=available_parameters,
        default=default,
        key=key,
        help=help_text
    )
    
    # Enforce max selections
    if max_selections and len(selected) > max_selections:
        st.warning(f"You can select a maximum of {max_selections} parameters. Only the first {max_selections} will be used.")
        selected = selected[:max_selections]
    
    return selected

def create_sortable_parameter_list(parameters: List[str],
                                  label: str = "Arrange Parameters",
                                  key: str = "param_sort") -> List[str]:
    """
    Create a sortable parameter list
    
    Args:
        parameters: List of parameters to sort
        label: Component label
        key: Streamlit widget key
    
    Returns:
        Sorted list of parameters
    """
    if not parameters:
        return []
    
    st.write(label)
    
    # Create a container for each parameter with up/down buttons
    sorted_params = parameters.copy()
    
    for i, param in enumerate(sorted_params):
        col1, col2, col3 = st.columns([0.8, 0.1, 0.1])
        
        with col1:
            st.text(param)
        
        with col2:
            if i > 0 and st.button("↑", key=f"{key}_up_{i}"):
                sorted_params[i], sorted_params[i-1] = sorted_params[i-1], sorted_params[i]
                st.experimental_rerun()
        
        with col3:
            if i < len(sorted_params) - 1 and st.button("↓", key=f"{key}_down_{i}"):
                sorted_params[i], sorted_params[i+1] = sorted_params[i+1], sorted_params[i]
                st.experimental_rerun()
    
    return sorted_params

def create_parameter_group_selector(parameters: Dict[str, List[str]],
                                   label: str = "Select Parameter Groups",
                                   key: str = "param_group") -> Dict[str, List[str]]:
    """
    Create a parameter group selector
    
    Args:
        parameters: Dictionary of parameter groups
        label: Component label
        key: Streamlit widget key
    
    Returns:
        Dictionary of selected parameter groups
    """
    if not parameters:
        return {}
    
    st.write(label)
    
    selected_groups = {}
    
    # Create an expander for each group
    for group_name, group_params in parameters.items():
        with st.expander(group_name):
            selected = st.multiselect(
                label=f"Select parameters from {group_name}",
                options=group_params,
                default=group_params,
                key=f"{key}_{group_name}"
            )
            
            if selected:
                selected_groups[group_name] = selected
    
    return selected_groups

# -----------------------------------------------------------------------------
# Advanced Search Components
# -----------------------------------------------------------------------------

def create_advanced_search(search_fields: List[Dict[str, Any]],
                          on_search: Callable[[Dict[str, Any]], None],
                          key: str = "adv_search") -> None:
    """
    Create an advanced search form
    
    Args:
        search_fields: List of search field configurations
        on_search: Callback function when search is performed
        key: Streamlit widget key
    """
    with st.form(key=f"{key}_form"):
        search_values = {}
        
        # Create fields based on configuration
        for field in search_fields:
            field_type = field.get("type", "text")
            field_key = field.get("key", "")
            field_label = field.get("label", field_key)
            field_options = field.get("options", [])
            field_default = field.get("default", None)
            field_help = field.get("help", "")
            
            if field_type == "text":
                search_values[field_key] = st.text_input(
                    label=field_label,
                    value=field_default or "",
                    key=f"{key}_{field_key}",
                    help=field_help
                )
            
            elif field_type == "number":
                search_values[field_key] = st.number_input(
                    label=field_label,
                    value=field_default or 0,
                    key=f"{key}_{field_key}",
                    help=field_help
                )
            
            elif field_type == "select":
                search_values[field_key] = st.selectbox(
                    label=field_label,
                    options=field_options,
                    index=field_options.index(field_default) if field_default in field_options else 0,
                    key=f"{key}_{field_key}",
                    help=field_help
                )
            
            elif field_type == "multiselect":
                search_values[field_key] = st.multiselect(
                    label=field_label,
                    options=field_options,
                    default=field_default if isinstance(field_default, list) else [],
                    key=f"{key}_{field_key}",
                    help=field_help
                )
            
            elif field_type == "date":
                search_values[field_key] = st.date_input(
                    label=field_label,
                    value=field_default or datetime.now().date(),
                    key=f"{key}_{field_key}",
                    help=field_help
                )
            
            elif field_type == "checkbox":
                search_values[field_key] = st.checkbox(
                    label=field_label,
                    value=field_default or False,
                    key=f"{key}_{field_key}",
                    help=field_help
                )
        
        # Add search button
        if st.form_submit_button("Search"):
            on_search(search_values)

def highlight_search_results(df: pd.DataFrame, 
                            search_term: str, 
                            columns: List[str] = None) -> pd.DataFrame:
    """
    Highlight search results in a DataFrame
    
    Args:
        df: DataFrame to highlight
        search_term: Search term
        columns: Columns to search (if None, search all string columns)
    
    Returns:
        Styled DataFrame with highlights
    """
    if not search_term or df.empty:
        return df.style
    
    # Determine columns to search
    if columns is None:
        columns = df.select_dtypes(include=['object']).columns.tolist()
    
    # Create style function
    def highlight_text(val):
        if not isinstance(val, str):
            return ""
        
        if search_term.lower() in val.lower():
            return "background-color: yellow"
        return ""
    
    # Apply style to selected columns
    return df.style.applymap(highlight_text, subset=columns)

def create_fuzzy_search(items: List[Dict[str, Any]],
                       search_keys: List[str],
                       label: str = "Search",
                       key: str = "fuzzy_search",
                       placeholder: str = "Type to search...",
                       min_score: float = 0.3) -> List[Dict[str, Any]]:
    """
    Create a fuzzy search component
    
    Args:
        items: List of items to search
        search_keys: Keys in items to search
        label: Search label
        key: Streamlit widget key
        placeholder: Placeholder text
        min_score: Minimum similarity score (0-1)
    
    Returns:
        List of matching items
    """
    search_query = st.text_input(
        label=label,
        key=key,
        placeholder=placeholder
    )
    
    if not search_query:
        return items
    
    # Perform fuzzy search
    results = []
    
    for item in items:
        # Calculate maximum similarity across all search keys
        max_score = 0
        
        for search_key in search_keys:
            if search_key in item:
                item_value = str(item[search_key]).lower()
                query = search_query.lower()
                
                # Simple fuzzy matching (more sophisticated algorithms could be used)
                if query in item_value:
                    # Direct substring match
                    score = 0.8 + 0.2 * (len(query) / len(item_value))
                else:
                    # Calculate similarity based on common characters
                    common_chars = sum(c in item_value for c in query)
                    score = common_chars / max(len(query), len(item_value))
                
                max_score = max(max_score, score)
        
        # Add to results if score is high enough
        if max_score >= min_score:
            item_copy = item.copy()
            item_copy['_score'] = max_score
            results.append(item_copy)
    
    # Sort by score
    results.sort(key=lambda x: x['_score'], reverse=True)
    
    return results

# -----------------------------------------------------------------------------
# Data Export Components
# -----------------------------------------------------------------------------

def create_export_button(data: Any,
                        label: str = "Export",
                        file_name: str = "export",
                        export_format: str = "csv",
                        key: str = "export_btn") -> None:
    """
    Create a button to export data
    
    Args:
        data: Data to export (DataFrame, dict, or list)
        label: Button label
        file_name: Export file name (without extension)
        export_format: Export format ('csv', 'json', 'excel')
        key: Streamlit widget key
    """
    # Convert data to appropriate format
    if export_format == "csv":
        if isinstance(data, pd.DataFrame):
            export_data = data.to_csv(index=False)
            mime = "text/csv"
            file_ext = "csv"
        else:
            try:
                export_data = pd.DataFrame(data).to_csv(index=False)
                mime = "text/csv"
                file_ext = "csv"
            except:
                st.error("Data cannot be exported as CSV")
                return
    
    elif export_format == "json":
        if isinstance(data, pd.DataFrame):
            export_data = data.to_json(orient="records")
        elif isinstance(data, (dict, list)):
            export_data = json.dumps(data, indent=2)
        else:
            try:
                export_data = json.dumps(data, indent=2)
            except:
                st.error("Data cannot be exported as JSON")
                return
        
        mime = "application/json"
        file_ext = "json"
    
    elif export_format == "excel":
        if isinstance(data, pd.DataFrame):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                data.to_excel(writer, index=False)
            
            export_data = output.getvalue()
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_ext = "xlsx"
        else:
            try:
                df = pd.DataFrame(data)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                export_data = output.getvalue()
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                file_ext = "xlsx"
            except:
                st.error("Data cannot be exported as Excel")
                return
    
    else:
        st.error(f"Unsupported export format: {export_format}")
        return
    
    # Create download button
    if isinstance(export_data, str):
        export_data = export_data.encode()
    
    b64 = base64.b64encode(export_data).decode()
    href = f'<a href="data:{mime};base64,{b64}" download="{file_name}.{file_ext}" class="streamlit-button primary-button">{label}</a>'
    st.markdown(href, unsafe_allow_html=True)

def create_export_options(data: Any,
                         file_name_prefix: str = "export",
                         key: str = "export_options") -> None:
    """
    Create export options with format selection
    
    Args:
        data: Data to export
        file_name_prefix: Prefix for export file name
        key: Streamlit widget key
    """
    with st.expander("Export Options"):
        col1, col2 = st.columns(2)
        
        with col1:
            export_format = st.selectbox(
                "Export Format",
                options=["CSV", "Excel", "JSON"],
                key=f"{key}_format"
            )
        
        with col2:
            file_name = st.text_input(
                "File Name",
                value=f"{file_name_prefix}_{datetime.now().strftime('%Y%m%d')}",
                key=f"{key}_filename"
            )
        
        # Create export button
        create_export_button(
            data=data,
            label=f"Download as {export_format}",
            file_name=file_name,
            export_format=export_format.lower(),
            key=f"{key}_btn"
        )

# -----------------------------------------------------------------------------
# Error Handling and Feedback Components
# -----------------------------------------------------------------------------

def show_success(message: str, icon: str = "✅", duration: int = 5):
    """
    Show a success message
    
    Args:
        message: Success message
        icon: Icon to display
        duration: Auto-dismiss duration in seconds (0 to disable)
    """
    if duration > 0:
        with st.success(f"{icon} {message}"):
            time.sleep(duration)
    else:
        st.success(f"{icon} {message}")

def show_info(message: str, icon: str = "ℹ️", duration: int = 0):
    """
    Show an info message
    
    Args:
        message: Info message
        icon: Icon to display
        duration: Auto-dismiss duration in seconds (0 to disable)
    """
    if duration > 0:
        with st.info(f"{icon} {message}"):
            time.sleep(duration)
    else:
        st.info(f"{icon} {message}")

def show_warning(message: str, icon: str = "⚠️", duration: int = 0):
    """
    Show a warning message
    
    Args:
        message: Warning message
        icon: Icon to display
        duration: Auto-dismiss duration in seconds (0 to disable)
    """
    if duration > 0:
        with st.warning(f"{icon} {message}"):
            time.sleep(duration)
    else:
        st.warning(f"{icon} {message}")

def show_error(message: str, icon: str = "❌", duration: int = 0):
    """
    Show an error message
    
    Args:
        message: Error message
        icon: Icon to display
        duration: Auto-dismiss duration in seconds (0 to disable)
    """
    if duration > 0:
        with st.error(f"{icon} {message}"):
            time.sleep(duration)
    else:
        st.error(f"{icon} {message}")

def create_progress_bar(total_steps: int, key: str = "progress") -> Callable[[int, str], None]:
    """
    Create a progress bar
    
    Args:
        total_steps: Total number of steps
        key: Streamlit widget key
    
    Returns:
        Function to update progress
    """
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(step: int, message: str = ""):
        """
        Update progress bar
        
        Args:
            step: Current step (0-based)
            message: Status message
        """
        progress = min(step / total_steps, 1.0)
        progress_bar.progress(progress)
        
        if message:
            status_text.text(f"{message} ({step}/{total_steps})")
    
    return update_progress

def create_status_indicator(statuses: Dict[str, Dict[str, Any]],
                           default_status: str = None,
                           key: str = "status") -> Callable[[str], None]:
    """
    Create a status indicator
    
    Args:
        statuses: Dictionary of status configurations
        default_status: Default status key
        key: Streamlit widget key
    
    Returns:
        Function to update status
    """
    status_container = st.empty()
    current_status = default_status
    
    def update_status(status: str):
        """
        Update status indicator
        
        Args:
            status: Status key
        """
        nonlocal current_status
        
        if status not in statuses:
            logger.warning(f"Unknown status: {status}")
            return
        
        status_config = statuses[status]
        icon = status_config.get("icon", "")
        message = status_config.get("message", status)
        color = status_config.get("color", "black")
        
        status_container.markdown(
            f'<div style="padding: 10px; border-radius: 5px; border: 1px solid {color}; color: {color};">{icon} {message}</div>',
            unsafe_allow_html=True
        )
        
        current_status = status
    
    # Set initial status if provided
    if default_status:
        update_status(default_status)
    
    return update_status

def error_boundary(func: Callable, fallback_ui: Callable = None, log_error: bool = True):
    """
    Create an error boundary around a UI component
    
    Args:
        func: Function to wrap with error boundary
        fallback_ui: Function to render in case of error
        log_error: Whether to log the error
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if log_error:
                logger.error(f"Error in UI component: {str(e)}")
                logger.error(traceback.format_exc())
            
            if fallback_ui:
                return fallback_ui(e)
            else:
                st.error(f"An error occurred: {str(e)}")
                with st.expander("Error details"):
                    st.code(traceback.format_exc())
    
    return wrapper

# -----------------------------------------------------------------------------
# Layout Helpers
# -----------------------------------------------------------------------------

def create_card(title: str, content: Callable, 
               icon: str = None, 
               is_expanded: bool = True,
               key: str = None):
    """
    Create a card with title and content
    
    Args:
        title: Card title
        content: Function to render card content
        icon: Optional icon for the title
        is_expanded: Whether the card is expanded by default
        key: Streamlit widget key
    """
    card_title = title
    if icon:
        card_title = f"{icon} {title}"
    
    with st.expander(card_title, expanded=is_expanded, key=key):
        content()

def create_tabs_card(tabs: Dict[str, Callable], 
                    default_tab: str = None,
                    key: str = "tabs_card"):
    """
    Create a card with tabs
    
    Args:
        tabs: Dictionary of tab titles and content functions
        default_tab: Default selected tab
        key: Streamlit widget key
    """
    if not tabs:
        return
    
    # Get tab titles
    tab_titles = list(tabs.keys())
    
    # Set default tab if not provided
    if default_tab is None and tab_titles:
        default_tab = tab_titles[0]
    
    # Create tabs
    tab_objects = st.tabs(tab_titles)
    
    # Render content for each tab
    for i, (title, content_func) in enumerate(tabs.items()):
        with tab_objects[i]:
            content_func()

def create_collapsible_sections(sections: Dict[str, Callable],
                              default_expanded: List[str] = None,
                              key: str = "sections"):
    """
    Create collapsible sections
    
    Args:
        sections: Dictionary of section titles and content functions
        default_expanded: List of section titles to expand by default
        key: Streamlit widget key
    """
    if not sections:
        return
    
    # Set default expanded sections if not provided
    if default_expanded is None:
        default_expanded = []
    
    # Create sections
    for i, (title, content_func) in enumerate(sections.items()):
        is_expanded = title in default_expanded
        section_key = f"{key}_{i}"
        
        with st.expander(title, expanded=is_expanded, key=section_key):
            content_func()

def create_grid_layout(items: List[Callable], 
                      cols: int = 3,
                      key: str = "grid"):
    """
    Create a grid layout
    
    Args:
        items: List of functions to render grid items
        cols: Number of columns
        key: Streamlit widget key
    """
    if not items:
        return
    
    # Create columns
    col_objects = st.columns(cols)
    
    # Render items in grid
    for i, item_func in enumerate(items):
        with col_objects[i % cols]:
            item_func()

def create_dashboard_metrics(metrics: Dict[str, Any], 
                           cols: int = 4,
                           key: str = "metrics"):
    """
    Create a dashboard metrics display
    
    Args:
        metrics: Dictionary of metric names and values
        cols: Number of columns
        key: Streamlit widget key
    """
    if not metrics:
        return
    
    # Create columns
    col_objects = st.columns(cols)
    
    # Display metrics
    for i, (metric_name, metric_value) in enumerate(metrics.items()):
        delta = None
        help_text = None
        
        # Check if metric value is a dictionary with additional info
        if isinstance(metric_value, dict):
            delta = metric_value.get("delta")
            help_text = metric_value.get("help")
            metric_value = metric_value.get("value")
        
        # Display metric
        with col_objects[i % cols]:
            st.metric(
                label=metric_name,
                value=metric_value,
                delta=delta,
                help=help_text,
                key=f"{key}_{i}"
            )

# Example usage
if __name__ == "__main__":
    st.title("UI Components Demo")
    
    st.header("Filter Components")
    
    # Create filter manager
    filter_mgr = FilterManager()
    filter_mgr.add_filter("supplier", "Supplier", ["Finisar", "Cisco", "Juniper"])
    filter_mgr.add_filter("product_family", "Product Family", ["Transceivers", "Switches", "Routers"])
    
    # Render filters
    active_filters = filter_mgr.render()
    
    st.write("Active Filters:", active_filters)
    
    st.header("Visualization Components")
    
    # Create sample data
    data = pd.DataFrame({
        "part_number": ["Part A", "Part B", "Part C", "Part D"],
        "supplier": ["Finisar", "Cisco", "Finisar", "Juniper"],
        "parameter_value": [10.3, 25.6, 5.2, 15.8],
        "unit": ["Gbps", "Gbps", "Gbps", "Gbps"],
        "confidence": [0.95, 0.85, 0.92, 0.78]
    })
    
    # Create chart
    fig = create_parameter_comparison_chart(data, "Data Rate")
    st.plotly_chart(fig, use_container_width=True)
    
    st.header("Export Components")
    
    # Create export options
    create_export_options(data, "parameter_comparison")
    
    st.header("Error Handling Components")
    
    # Create status indicator
    statuses = {
        "idle": {"icon": "⏳", "message": "Waiting for input", "color": "gray"},
        "processing": {"icon": "🔄", "message": "Processing...", "color": "blue"},
        "success": {"icon": "✅", "message": "Operation completed", "color": "green"},
        "error": {"icon": "❌", "message": "An error occurred", "color": "red"}
    }
    
    update_status = create_status_indicator(statuses, "idle")
    
    # Demonstrate status changes
    if st.button("Simulate Process"):
        update_status("processing")
        time.sleep(2)
        update_status("success")
