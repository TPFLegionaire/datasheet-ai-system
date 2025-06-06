import streamlit as st

st.title("🚀 Datasheet AI System")
st.write("Welcome! The app is deploying successfully.")

# Simple test features
tab1, tab2 = st.tabs(["📊 Status", "📤 Demo"])

with tab1:
    st.success("✅ App is running!")
    st.metric("Status", "Online")
    st.metric("Version", "1.0")

with tab2:
    st.header("Demo Upload")
    file = st.file_uploader("Test upload", type=['pdf'])
    if file:
        st.success(f"Received: {file.name}")
