import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from collections import Counter
import ast # Used to safely convert string representations of lists (e.g. "['Tag1', 'Tag2']") back into Python lists

# --- Pydantic Imports for Validation ---
from pydantic import TypeAdapter, HttpUrl, ValidationError

# --- Project Imports ---
from src.config import settings
from src.database.connection import SessionLocal
from src.database.models import ScheduledJob

# ==========================================
# 1. PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(
    page_title="AI Scraper Dashboard", 
    layout="wide", 
    page_icon="🕷️"
)

# Custom CSS for the Visual Feed (Cards, Badges, Pills)
st.markdown("""
<style>
    /* Card Container */
    .card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        background-color: #ffffff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
    }
    .card:hover {
        transform: translateY(-3px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    /* Category Badge (Blue) */
    .badge-category {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75em;
        font-weight: 600;
        background-color: #dbeafe;
        color: #1e3a8a;
        margin-right: 5px;
    }
    
    /* Urgency Badge (Red/Yellow/Green dynamic) */
    .badge-urgent {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75em;
        font-weight: 600;
        color: #7f1d1d;
        margin-left: 5px;
    }
    .urgent-high { background-color: #fee2e2; color: #991b1b; }
    .urgent-medium { background-color: #fef3c7; color: #854d0e; }
    .urgent-low { background-color: #ecfdf5; color: #065f46; }
    
    /* Hash Tags */
    .tag-pill {
        display: inline-block;
        background-color: #f3f4f6;
        color: #4b5563;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.75em;
        margin-right: 4px;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🕷️ AI-Powered Intelligence Dashboard")

# ==========================================
# 2. DATABASE CONNECTION & DATA LOADING
# ==========================================
@st.cache_resource
def get_engine():
    return create_engine(settings.DB_URL)

engine = get_engine()

@st.cache_data(ttl=60) # Cache data for 60 seconds
def load_data():
    try:
        # Fetch only processed articles (where AI category exists)
        query = """
            SELECT id, url, title, created_at, 
                   ai_category, ai_urgency, ai_tags, 
                   summary, main_image, author
            FROM scraped_data 
            WHERE ai_category IS NOT NULL 
            ORDER BY created_at DESC
            LIMIT 100
        """
        df = pd.read_sql(query, engine)
        
        # --- Helper to parse the tags string back to list ---
        def parse_tags(tag_str):
            if not tag_str: return []
            try:
                # If it's already a list (unlikely from SQL but possible), return it
                if isinstance(tag_str, list): return tag_str
                # Safely evaluate string "['a', 'b']" to list ['a', 'b']
                return ast.literal_eval(tag_str)
            except:
                return []

        df['ai_tags'] = df['ai_tags'].apply(parse_tags)
        
        # Ensure urgency is numeric for calculations
        df['ai_urgency'] = pd.to_numeric(df['ai_urgency'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# Refresh Button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 3. SIDEBAR: CONTROL PANEL (Scraper & Scheduler)
# ==========================================
with st.sidebar:
    st.header("⚙️ Control Panel")
    
    # --- PART A: MANUAL SCRAPER ---
    with st.expander("🚀 Launch Scraper", expanded=True):
        url_input = st.text_area("Enter URLs (one per line):", height=100)
        
        if st.button("Start Scraping"):
            if url_input:
                from src.scraper.tasks import app as celery_app
                
                # --- Pydantic Validation Logic ---
                url_adapter = TypeAdapter(HttpUrl)
                urls = url_input.strip().split('\n')
                
                valid_count = 0
                invalid_urls = []
                
                for raw_url in urls:
                    url_str = raw_url.strip()
                    if not url_str: continue
                    
                    try:
                        # Validate
                        url_adapter.validate_python(url_str)
                        # Send Task
                        celery_app.send_task('src.scraper.tasks.scrape_task', args=[url_str])
                        valid_count += 1
                    except ValidationError:
                        invalid_urls.append(url_str)
                
                if valid_count > 0:
                    st.success(f"Queued {valid_count} tasks!")
                if invalid_urls:
                    st.error(f"Invalid URLs: {len(invalid_urls)}")
            else:
                st.warning("Enter a URL first.")

    st.divider()

    # --- PART B: SCHEDULER MANAGEMENT ---
    st.subheader("🕒 Manage Schedules")
    
    # 1. Add New Schedule
    with st.form("new_schedule"):
        s_name = st.text_input("Name", placeholder="e.g. Daily Tech News")
        s_url = st.text_input("URL", placeholder="https://example.com")
        s_int = st.number_input("Interval (sec)", min_value=60, value=3600, step=60)
        
        if st.form_submit_button("Create Schedule"):
            if s_name and s_url:
                db_add = SessionLocal()
                try:
                    job = ScheduledJob(name=s_name, url=s_url, interval_seconds=s_int, is_active=True)
                    db_add.add(job)
                    db_add.commit()
                    st.success("Saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    db_add.close()
    
    # 2. List & Edit Schedules
    db_sched = SessionLocal()
    try:
        jobs = db_sched.query(ScheduledJob).order_by(ScheduledJob.created_at.desc()).all()
        if jobs:
            st.write("---")
            job_opts = {f"{j.id}. {j.name}": j.id for j in jobs}
            sel_job = st.selectbox("Select Task:", ["-- Select --"] + list(job_opts.keys()))
            
            if sel_job != "-- Select --":
                jid = job_opts[sel_job]
                # FIX: explicit generator
                jobj = next(j for j in jobs if j.id == jid) # type: ignore
                
                c1, c2 = st.columns(2)
                if c1.button("Toggle Active", key=f"tog_{jid}"):
                    # FIX: Explicit boolean cast or ignore to satisfy static analysis
                    jobj.is_active = not bool(jobj.is_active)  # type: ignore
                    db_sched.commit()
                    st.rerun()
                
                if c2.button("Delete", key=f"del_{jid}", type="primary"):
                    db_sched.delete(jobj)
                    db_sched.commit()
                    st.rerun()
                
                # FIX: Explicit boolean cast
                is_active_status = bool(jobj.is_active)
                st.caption(f"Status: {'✅ Active' if is_active_status else '❌ Inactive'}")
                st.caption(f"Interval: {jobj.interval_seconds}s")
    finally:
        db_sched.close()

# ==========================================
# 4. MAIN CONTENT: ANALYTICS
# ==========================================
df = load_data()

if not df.empty:
    # --- High Level Metrics ---
    st.header("📊 AI Insights")
    
    m1, m2, m3 = st.columns(3)
    
    total_arts = len(df)
    avg_urg = df['ai_urgency'].mean()
    # Handle empty mode if no categories exist yet
    top_cat = df['ai_category'].mode()[0] if not df['ai_category'].mode().empty else "N/A"
    
    m1.metric("Processed Articles", total_arts)
    m2.metric("Avg Urgency", f"{avg_urg:.1f}/10")
    m3.metric("Top Category", top_cat)
    
    st.divider()
    
    # --- Plotly Charts ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Content Mix")
        if not df['ai_category'].dropna().empty:
            cat_counts = df['ai_category'].value_counts()
            fig_pie = px.pie(values=cat_counts.values, names=cat_counts.index, hole=0.4)
            st.plotly_chart(fig_pie, width="stretch")
            
    with c2:
        st.subheader("Urgency Histogram")
        if not df['ai_urgency'].dropna().empty:
            fig_hist = px.histogram(df, x="ai_urgency", nbins=10, 
                                    color_discrete_sequence=['#636EFA'], title="Distribution of Scores")
            fig_hist.update_layout(bargap=0.1)
            st.plotly_chart(fig_hist, width="stretch")
            
    # --- Trending Tags Bar Chart ---
    st.subheader("🏷️ Top 15 Trending Tags")
    # Flatten the list of lists: [['A','B'], ['A','C']] -> ['A','B','A','C']
    all_tags = [tag for tags in df['ai_tags'] for tag in tags]
    
    if all_tags:
        tag_counts = Counter(all_tags).most_common(15)
        tag_df = pd.DataFrame(tag_counts, columns=['Tag', 'Count'])
        fig_bar = px.bar(tag_df, x='Count', y='Tag', orientation='h', color='Count')
        st.plotly_chart(fig_bar, width="stretch")

    st.divider()

    # ==========================================
    # 5. VISUAL NEWS FEED (Cards)
    # ==========================================
    st.header("📰 Intelligence Feed")
    
    # Filter Slider
    min_urg = st.slider("Filter by Urgency:", 1, 10, 1)
    filtered_df = df[df['ai_urgency'] >= min_urg]
    
    st.caption(f"Showing {len(filtered_df)} articles")
    
    # Grid Layout (3 Columns)
    cols = st.columns(3)
    
    # FIX: Use enumerate() to get a clean integer index 'i'
    # iterrows() returns (index, Series), and index might not be an integer.
    for i, (_, row) in enumerate(filtered_df.iterrows()):
        
        # Determine styling based on urgency
        u_score = row['ai_urgency']
        u_class = "urgent-high" if u_score >= 8 else "urgent-medium" if u_score >= 5 else "urgent-low"
        border_col = "#991b1b" if u_score >= 8 else "#eab308" if u_score >= 5 else "#10b981"
        
        # Safe Summary Truncation
        summary_text = row['summary'] if row['summary'] else "No summary available."
        if len(summary_text) > 150: summary_text = summary_text[:150] + "..."
        
        # Tags HTML Generation
        tags_html = "".join([f'<span class="tag-pill">#{t}</span>' for t in row['ai_tags'][:3]]) # Show max 3 tags
        
        card_html = f"""
        <div class="card" style="border-left: 5px solid {border_col};">
            <div style="display:flex; justify-content:space-between;">
                <h4 style="margin:0; font-size:1.1em;">{row['title'][:50]}...</h4>
                <span class="badge-urgent {u_class}">{int(u_score)}</span>
            </div>
            <div style="margin-top:5px; margin-bottom:10px;">
                <span class="badge-category">{row['ai_category']}</span>
            </div>
            <p style="font-size:0.9em; color:#444;">{summary_text}</p>
            <div style="margin-bottom:10px;">{tags_html}</div>
            <div style="margin-top:auto; font-size:0.8em; color:gray; display:flex; justify-content:space-between;">
                <span>{row['created_at'].strftime('%m-%d %H:%M')}</span>
                <a href="{row['url']}" target="_blank" style="color:#2563eb; text-decoration:none;">Read &rarr;</a>
            </div>
        </div>
        """
        
        # Add to column (Round Robin) using the integer index 'i'
        with cols[i % 3]:
            st.markdown(card_html, unsafe_allow_html=True)

else:
    st.info("No AI-analyzed data available yet. Add a URL in the sidebar to start!")