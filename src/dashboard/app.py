import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from pydantic import TypeAdapter, HttpUrl, ValidationError # <--- for validation step

from src.config import settings

# 1. Setup Page
st.set_page_config(page_title="Scraper Dashboard", layout="wide")
st.title("🕷️ Scraper Dashboard")

# 2. Connect to Database
@st.cache_resource
def get_engine():
    return create_engine(settings.DB_URL)

engine = get_engine()

# 3. Fetch Data
def load_data():
    try:
        query = "SELECT id, url, title, created_at, content FROM scraped_data ORDER BY created_at DESC"
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        st.error(f"Error connecting to DB: {e}")
        return pd.DataFrame()

# 4. Refresh Button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

# --- NEW SECTION: BULK ADD ---
st.sidebar.header("Add New Source(s)")
# Changed from text_input to text_area for multiple lines
url_input = st.sidebar.text_area("Enter URLs (one per line):", height=150)

if st.sidebar.button("🚀 Launch Scraper"):
    if url_input:
        from src.scraper.tasks import app as celery_app
        
        # Pydantic V2 Adapter for URL validation
        url_adapter = TypeAdapter(HttpUrl)
        
        urls = url_input.strip().split('\n')
        
        valid_count = 0
        invalid_urls = []
        
        for raw_url in urls:
            url_str = raw_url.strip()
            if not url_str:
                continue # Skip empty lines
                
            try:
                # 1. Validate URL
                # If invalid, this raises ValidationError
                url_adapter.validate_python(url_str)
                
                # 2. Queue Task (Only if valid)
                celery_app.send_task('src.scraper.tasks.scrape_task', args=[url_str])
                valid_count += 1
                
            except ValidationError:
                invalid_urls.append(url_str)
        
        # 3. User Feedback
        if valid_count > 0:
            st.sidebar.success(f"✅ Queued {valid_count} tasks!")
            
        if invalid_urls:
            st.sidebar.error(f"❌ Skipped {len(invalid_urls)} invalid URLs:")
            for bad_url in invalid_urls:
                st.sidebar.caption(f"- {bad_url}")
                
    else:
        st.sidebar.warning("Please enter at least one URL.")
# -----------------------------------------
# 5. Display Stats
df = load_data()

# --- ANALYTICS SECTION ---
if not df.empty:
    st.subheader("📊 Analytics: Links per Page")
    
    # 1. Extract 'links_found' from the JSON content column
    # We use a lambda function to dig into the dictionary
    df['link_count'] = df['content'].apply(lambda x: x.get('links_found', 0) if x else 0)
    
    # 2. Create a clean subset for the chart
    chart_data = df[['url', 'link_count']].copy()
    chart_data.set_index('url', inplace=True)
    
    # 3. Render the Chart
    st.bar_chart(chart_data)
# -------------------------

# 6. Display Table
st.subheader("Recent Data")
if not df.empty:
    # Show the table
    st.dataframe(df)
    
    # Show raw JSON for selected row
    st.subheader("Inspect Content (JSON)")
    selected_id = st.selectbox("Select ID to inspect:", df['id'])
    if selected_id:
        row = df[df['id'] == selected_id].iloc[0]
        st.json(row['content'])
else:
    st.info("No data found yet. Run some tasks!")