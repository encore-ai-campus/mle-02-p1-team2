"""Entry-point-local styling; never writes Streamlit theme configuration."""
import streamlit as st


def apply_style():
    st.html("""
    <style>
    .stApp:has(.st-key-preventra) { background: #f8fbfb; color: #173047; color-scheme: light; }
    .stApp:has(.st-key-preventra) header[data-testid="stHeader"] { background: #f8fbfb; }
    .stApp:has(.st-key-preventra) [data-testid="stSidebar"] { background: #eef4f5; border-right: 1px solid #dce7e9; }
    .stApp:has(.st-key-preventra) .block-container { max-width: 1250px; padding-top: 4.5rem; padding-bottom: 3rem; }
    .st-key-preventra, .st-key-preventra_sidebar { font-family: Inter, "Noto Sans KR", system-ui, sans-serif; color: #173047; }
    .st-key-preventra h1, .st-key-preventra h2, .st-key-preventra h3,
    .st-key-preventra_sidebar h2, .st-key-preventra_sidebar h3 { color: #173047; letter-spacing: -.035em; }
    .st-key-preventra p, .st-key-preventra label, .st-key-preventra_sidebar p { color: #173047; }
    .st-key-preventra [data-testid="stCaptionContainer"] p,
    .st-key-preventra_sidebar [data-testid="stCaptionContainer"] p { color: #586d7a; }
    .st-key-preventra button, .st-key-preventra_sidebar button { border-radius: 10px; min-height: 44px; box-shadow: none; background: white; color: #173047; border-color: #d2dfe3; }
    .st-key-preventra button[kind^="primary"], .st-key-preventra_sidebar button[kind^="primary"] { background: #087c76; color: white; border-color: #087c76; }
    .st-key-preventra button[kind^="primary"] p, .st-key-preventra_sidebar button[kind^="primary"] p { color: white; }
    .st-key-preventra button:hover, .st-key-preventra_sidebar button:hover { border-color: #087c76; }
    .st-key-preventra input, .st-key-preventra textarea { color: #173047; background: #fff; }
    .st-key-preventra [data-baseweb="input"], .st-key-preventra [data-baseweb="select"] > div { background: #fff; color: #173047; border-color: #d2dfe3; }
    .st-key-preventra [data-testid="stForm"] { background: #fff; border: 1px solid #cbdedf; border-radius: 16px; padding: 1.15rem; }
    .st-key-preventra [data-testid="stMetric"] { background: #fff; padding: 1rem; border: 1px solid #dce7e9; border-radius: 12px; }
    .st-key-preventra [data-testid="stMetricValue"] { color: #173047; }
    .st-key-preventra [data-testid="stChatMessage"] { background: #eef5f5; border-radius: 14px; }
    .stApp:has(.st-key-preventra) [data-testid="stBottomBlockContainer"] { background: #f8fbfb; }
    .stApp:has(.st-key-preventra) [data-testid="stChatInput"] { background: white; border-color: #b7d6d5; color: #173047; }
    .stApp:has(.st-key-preventra) [data-testid="stChatInput"] textarea { color: #173047; }
    .pv-brand { font-size: 1.6rem; font-weight: 750; letter-spacing: -.06em; }
    .pv-brand span { color: #09877f; }
    .pv-eyebrow { color: #087c76; font-size: .8rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
    .pv-hero { padding: 3rem 0 1.2rem; }
    .pv-hero h1 { font-size: clamp(2.5rem, 4.6vw, 4rem); line-height: 1.12; margin: .75rem 0 1.2rem; font-weight: 740; }
    .pv-hero h1 span { color: #087c76; }
    .pv-hero p { font-size: 1.05rem; line-height: 1.85; max-width: 710px; }
    .pv-card { background: #fff; border: 1px solid #dce7e9; border-radius: 16px; padding: 1.5rem; min-height: 185px; }
    .pv-card h3 { font-size: 1.15rem; margin: .65rem 0; }
    .pv-card p { font-size: .95rem; line-height: 1.7; }
    .pv-footer { border-top: 1px solid #dce7e9; margin-top: 3rem; padding-top: 1.5rem; }
    .pv-empty { padding: 1.25rem; border: 1px dashed #bfd2d7; border-radius: 12px; color: #586d7a; font-size: .9rem; line-height: 1.8; }
    @media (max-width: 700px) { .pv-hero { padding-top: 1.5rem; } .pv-card { min-height: auto; } }
    </style>
    """)
