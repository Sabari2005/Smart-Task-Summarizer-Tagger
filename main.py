import os
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from schema import TaskInput, TaskOutput, PriorityLevel, TagCategory
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich import box
from dotenv import load_dotenv
import logging
import streamlit as st
from streamlit_lottie import st_lottie
import json
import time
from typing import List
from schema import TaskInput
import pandas as pd

# Configuration
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()



def load_lottie_file(filepath: str):
    with open(filepath, "r") as f:
        return json.load(f)

# Groq LLM Configuration
groq_llm = ChatGroq(
    temperature=0.2,  # More deterministic output
    model_name="llama3-70b-8192",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    max_retries=3,
    request_timeout=30
)

# System Prompts
SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
Transform this task into a 10-15 word actionable summary. Be specific about actions and timing.
Example: "Schedule team meeting for Wednesday 3pm in conference room B"

Task: {raw_text}

Summary must be 10-15 words:""")

TAGS_PROMPT = ChatPromptTemplate.from_template("""
Classify this task into relevant categories from this list: 
{tag_options}. Choose 1-3 most relevant tags. Respond with JSON array only.

Task: {raw_text}

Tags:""")

PRIORITY_PROMPT = ChatPromptTemplate.from_template("""
Analyze this task and assign priority considering:
1. Urgency (time sensitivity)
2. Impact (consequences if not done)
3. Effort required
Use this scale: low, medium, high, critical

Respond with ONLY valid JSON in this format:
{{ "priority": "value", "confidence": 0.0-1.0 }}

Do not include any explanation or extra text.

Task: {raw_text}
""")

def process_task(task: TaskInput) -> TaskOutput:
    start_time = time.time()
    
    processing_chain = RunnableParallel(
        summary=SUMMARY_PROMPT | groq_llm | JsonOutputParser(),
        tags=TAGS_PROMPT.partial(tag_options=[t.value for t in TagCategory]) | groq_llm | JsonOutputParser(),
        priority=PRIORITY_PROMPT | groq_llm | JsonOutputParser(),
        original_text=RunnablePassthrough()
    )
    
    result = processing_chain.invoke({"raw_text": task.raw_text})
    processing_time_ms = (time.time() - start_time) * 1000
    
    # Handle priority response (could be string or dict)
    priority_data = result["priority"]
    if isinstance(priority_data, dict):
        priority = priority_data.get("priority", "").lower()
        confidence = priority_data.get("confidence", 0.8)
    else:
        priority = str(priority_data).lower()
        confidence = 0.8  # Default confidence
    
    return TaskOutput(
        summary=result["summary"],
        tags=[TagCategory(tag.lower()) for tag in result["tags"]],
        priority=PriorityLevel(priority),
        original_text=task.raw_text,
        processing_time_ms=round(processing_time_ms, 2),
        confidence_score=float(confidence)
    )

def display_tasks(tasks: List[TaskOutput]):
    table = Table(title="Processed Tasks", box=box.ROUNDED, show_lines=True)
    table.add_column("Summary", width=40)
    table.add_column("Tags", width=20)
    table.add_column("Priority", width=12)
    table.add_column("Confidence", width=10)
    table.add_column("Original", width=30)
    
    for task in tasks:
        # Color coding for priority
        priority_color = {
            "low": "blue",
            "medium": "green",
            "high": "yellow",
            "critical": "red"
        }.get(task.priority.value, "white")
        
        table.add_row(
            task.summary,
            ", ".join([f"[cyan]{t.value}[/cyan]" for t in task.tags]),
            f"[{priority_color}]{task.priority.value.upper()}[/{priority_color}]",
            f"{task.confidence_score:.2f}",
            task.original_text[:30] + ("..." if len(task.original_text) > 30 else "")
        )
    console.print(table)

def streamlit_ui():
    # Custom CSS for animations and styling
    st.markdown("""
    <style>
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .fade-in {
            animation: fadeIn 0.5s ease-out forwards;
        }
        .priority-low {
            background-color: #e6f7ff;
            padding: 8px;
            border-radius: 8px;
            border-left: 4px solid #1890ff;
        }
        .priority-medium {
            background-color: #f6ffed;
            padding: 8px;
            border-radius: 8px;
            border-left: 4px solid #52c41a;
        }
        .priority-high {
            background-color: #fff7e6;
            padding: 8px;
            border-radius: 8px;
            border-left: 4px solid #faad14;
        }
        .priority-critical {
            background-color: #fff1f0;
            padding: 8px;
            border-radius: 8px;
            border-left: 4px solid #f5222d;
        }
        .task-card {
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 16px;
            transition: transform 0.3s ease;
            background-color: #181e18;
        }
        .task-card:hover {
            transform: translateY(-5px);
        }
        .stProgress > div > div > div {
            background-color: #5e35b1;
        }
        .export-buttons {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
    </style>
    """, unsafe_allow_html=True)

    # App layout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("✨ Smart Task Summarizer")
        st.markdown("Transform messy tasks into clear, actionable items with AI-powered processing.")
    with col2:
        # Load and display Lottie animation
        lottie_animation = load_lottie_file("animation.json")  # Replace with your animation file
        st_lottie(lottie_animation, height=100, key="header-animation")

    # Input section
    with st.expander("📝 Enter your tasks", expanded=True):
        user_input = st.text_area(
            "Paste your messy tasks (one per line)", 
            height=200,
            placeholder="Example:\nNeed to talk to team about project timeline\nBuy milk and eggs\nSchedule dentist appointment",
            key="task_input"
        )
        
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            process_btn = st.button("🚀 Process Tasks", use_container_width=True)

    # Initialize session state for processed tasks
    if 'processed_tasks' not in st.session_state:
        st.session_state.processed_tasks = []

    # Processing animation
    if process_btn and user_input.strip():
        tasks = [t.strip() for t in user_input.split("\n") if t.strip()]
        
        with st.spinner("Processing your tasks..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            processed = []
            for i, task in enumerate(tasks):
                try:
                    # Simulate processing (replace with actual processing)
                    time.sleep(0.5)  # Remove this in production
                    result = process_task(TaskInput(raw_text=task))
                    processed.append(result)
                    
                    # Update progress
                    progress = (i + 1) / len(tasks)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing task {i+1} of {len(tasks)}...")
                except Exception as e:
                    st.error(f"Failed to process: {task[:50]}...")
            
            progress_bar.empty()
            status_text.empty()
            
            # Show completion animation
            st.balloons()
            
            # Store processed tasks in session state
            st.session_state.processed_tasks = processed
            
            # Display results with animations
            st.success(f"✅ Processed {len(processed)} tasks successfully!")

    # Display results if we have processed tasks
    if st.session_state.processed_tasks:
        # Results tabs
        tab1, tab2 = st.tabs(["📋 Task List", "📊 Summary"])
        
        with tab1:
            for i, task in enumerate(st.session_state.processed_tasks):
                # Determine priority class
                priority_class = f"priority-{task.priority.value.lower()}"
                
                # Animated card for each task
                st.markdown(f"""
                <div class="task-card fade-in {priority_class}" style="animation-delay: {i*0.1}s">
                    <h3>Task {i+1}</h3>
                    <p><strong>📝 Summary:</strong> {task.summary}</p>
                    <div style="display: flex; gap: 16px; margin-top: 8px;">
                        <div><strong>🏷️ Tags:</strong> {", ".join(t.value for t in task.tags)}</div>
                        <div><strong>🔢 Priority:</strong> {task.priority.value.upper()}</div>
                        <div><strong>🕒 Processing Time:</strong> {task.processing_time_ms}ms</div>
                    </div>
                    <details style="margin-top: 8px;">
                        <summary>Original text</summary>
                        <p>{task.original_text}</p>
                    </details>
                </div>
                """, unsafe_allow_html=True)
        
        with tab2:
            # Summary statistics
            priority_counts = {}
            tag_counts = {}
            
            for task in st.session_state.processed_tasks:
                priority = task.priority.value
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
                
                for tag in task.tags:
                    tag_counts[tag.value] = tag_counts.get(tag.value, 0) + 1
            
            # Priority distribution
            st.subheader("Priority Distribution")
            cols = st.columns(len(priority_counts))
            for i, (priority, count) in enumerate(priority_counts.items()):
                with cols[i]:
                    st.metric(
                        label=f"{priority.upper()}",
                        value=count,
                        help=f"{count} {priority} priority tasks"
                    )
            
            # Tags cloud
            st.subheader("Tags Frequency")
            tag_cloud = " ".join(
                [f"<span style='font-size:{count * 1.2}em; margin-right: 8px;'>{tag}</span>" 
                 for tag, count in tag_counts.items()]
            )
            st.markdown(f"<div style='line-height: 2.5;'>{tag_cloud}</div>", unsafe_allow_html=True)
            
            # Processing stats
            avg_time = sum(t.processing_time_ms for t in st.session_state.processed_tasks) / len(st.session_state.processed_tasks)
            st.metric("Average Processing Time", f"{avg_time:.2f}ms")

        # Export section
        st.markdown("---")
        st.subheader("📤 Export Options")
        
        # Create export data
        export_data = []
        for task in st.session_state.processed_tasks:
            export_data.append({
                "summary": task.summary,
                "tags": ", ".join(t.value for t in task.tags),
                "priority": task.priority.value.upper(),
                "confidence_score": task.confidence_score,
                "processing_time_ms": task.processing_time_ms,
                "original_text": task.original_text
            })
        
        col1, col2 = st.columns(2)
        
        with col1:
            # JSON Export
            json_data = json.dumps(export_data, indent=2)
            st.download_button(
                label="⬇️ Download as JSON",
                data=json_data,
                file_name="processed_tasks.json",
                mime="application/json",
                help="Download all processed tasks in JSON format"
            )
        
        with col2:
            # CSV Export
            df = pd.DataFrame(export_data)
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download as CSV",
                data=csv_data,
                file_name="processed_tasks.csv",
                mime="text/csv",
                help="Download all processed tasks in CSV format"
            )
        
        # Preview of export data
        with st.expander("🔍 Preview Export Data"):
            st.write("### JSON Preview")
            st.code(json_data, language='json')
            
            st.write("### CSV Preview")
            st.dataframe(df)

if __name__ == "__main__":
    streamlit_ui()

